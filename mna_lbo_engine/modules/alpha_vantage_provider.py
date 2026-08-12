"""Alpha Vantage data provider, caching engine, and circuit breaker.

This module is a data-access adapter only. It deliberately contains no
valuation, transaction, risk, or validation methodology.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import threading
import time
from typing import Any
import os

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

BASE_URL = "https://www.alphavantage.co/query"
CACHE_TTL_SECONDS = 900.0  # 15 minute TTL
MIN_REQUEST_INTERVAL_SECONDS = 1.25
MAX_ATTEMPTS = 3
CIRCUIT_BREAKER_COOLDOWN_SECONDS = 60.0  # 60 second circuit breaker cooldown


class AlphaVantageError(RuntimeError):
    """Base provider error suitable for safe, user-facing fallback handling."""


class AlphaVantageUnavailable(AlphaVantageError):
    """Raised for missing credentials, throttling, transport, and API errors."""


class AlphaVantageRateLimited(AlphaVantageError):
    """Raised when Alpha Vantage rate limit is hit or circuit breaker is active."""


class AlphaVantageInvalidTicker(AlphaVantageError):
    """Raised when Alpha Vantage cannot identify the requested company."""


def _number(value: Any) -> float | None:
    """Preserve absent/provider-null values as None; numeric zero remains zero."""
    if value is None or value == "" or value == "None":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_report(payload: dict[str, Any]) -> dict[str, Any]:
    reports = payload.get("annualReports")
    if not isinstance(reports, list) or not reports or not isinstance(reports[0], dict):
        return {}
    return reports[0]


def _outflow(value: Any) -> float | None:
    """Normalize provider cash-flow sign convention to the existing outflow field."""
    parsed = _number(value)
    return abs(parsed) if parsed is not None else None


class AlphaVantageProvider:
    """Centralized, cached, thread-safe Alpha Vantage client with Rate-Limit Circuit Breaker."""

    def __init__(
        self,
        api_key: str | None = None,
        session: requests.Session | None = None,
        timeout_seconds: float = 25.0,
        min_request_interval_seconds: float = MIN_REQUEST_INTERVAL_SECONDS,
        circuit_breaker_cooldown_seconds: float = CIRCUIT_BREAKER_COOLDOWN_SECONDS,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds
        self.min_request_interval_seconds = min_request_interval_seconds
        self.circuit_breaker_cooldown_seconds = circuit_breaker_cooldown_seconds
        self._pace_requests = session is None and min_request_interval_seconds > 0
        self._last_request_at = 0.0
        self._circuit_breaker_tripped_until = 0.0
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._endpoint_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
        self._failure_cache: dict[str, tuple[float, type[AlphaVantageError], str]] = {}

    def is_circuit_breaker_active(self) -> bool:
        """Returns True if the rate-limit circuit breaker is currently open/cooldown."""
        return time.monotonic() < self._circuit_breaker_tripped_until

    def _trip_circuit_breaker(self, reason: str = "Rate limit detected") -> None:
        """Trip global circuit breaker to stop further provider calls for cooldown duration."""
        self._circuit_breaker_tripped_until = time.monotonic() + self.circuit_breaker_cooldown_seconds
        logger.warning(
            "Rate-limit circuit breaker TRIPPED for %.1fs: %s",
            self.circuit_breaker_cooldown_seconds,
            reason,
        )

    def _request(self, function: str, ticker: str) -> dict[str, Any]:
        if not self.api_key:
            raise AlphaVantageUnavailable("Alpha Vantage API key is not configured.")

        if self.is_circuit_breaker_active():
            remaining = self._circuit_breaker_tripped_until - time.monotonic()
            raise AlphaVantageRateLimited(
                f"Alpha Vantage rate-limit circuit breaker active ({remaining:.1f}s cooldown remaining)."
            )

        cache_key = (ticker, function)
        cached_endpoint = self._endpoint_cache.get(cache_key)
        if cached_endpoint and time.monotonic() - cached_endpoint[0] < CACHE_TTL_SECONDS:
            logger.info("Using cached Alpha Vantage endpoint response: function=%s ticker=%s", function, ticker)
            return cached_endpoint[1]

        logger.info("Executing Alpha Vantage API request: function=%s ticker=%s", function, ticker)
        last_error_msg: str = "Request failed"

        for attempt in range(MAX_ATTEMPTS):
            self._wait_for_rate_limit()
            try:
                response = self.session.get(
                    BASE_URL,
                    params={"function": function, "symbol": ticker, "apikey": self.api_key},
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error_msg = f"Transport/HTTP error: {type(exc).__name__}"
                logger.warning(
                    "Alpha Vantage request attempt %d/%d failed for function=%s ticker=%s: %s",
                    attempt + 1,
                    MAX_ATTEMPTS,
                    function,
                    ticker,
                    last_error_msg,
                )
                self._backoff(attempt)
                continue

            if not isinstance(payload, dict):
                last_error_msg = "Malformed JSON payload"
                logger.warning("Alpha Vantage returned non-dict JSON for function=%s ticker=%s", function, ticker)
                raise AlphaVantageUnavailable("Alpha Vantage returned a malformed response.")

            provider_message = payload.get("Note") or payload.get("Information")
            if provider_message:
                last_error_msg = f"Provider rate limit message: {str(provider_message)[:100]}"
                logger.warning(
                    "Alpha Vantage rate limit message on attempt %d/%d for function=%s ticker=%s: %s",
                    attempt + 1,
                    MAX_ATTEMPTS,
                    function,
                    ticker,
                    last_error_msg,
                )
                if self._is_rate_limit_message(provider_message):
                    self._trip_circuit_breaker(str(provider_message)[:100])
                    raise AlphaVantageRateLimited(f"Alpha Vantage rate limit reached: {str(provider_message)[:100]}")
                raise AlphaVantageUnavailable("Alpha Vantage request limit or provider error.")

            if payload.get("Error Message"):
                logger.warning("Alpha Vantage Error Message for function=%s ticker=%s", function, ticker)
                raise AlphaVantageInvalidTicker("Alpha Vantage did not recognize the requested ticker.")

            # Store in endpoint cache
            self._endpoint_cache[cache_key] = (time.monotonic(), payload)
            return payload

        raise AlphaVantageUnavailable(f"Alpha Vantage request failed for function={function}: {last_error_msg}")

    def _wait_for_rate_limit(self) -> None:
        if not self._pace_requests:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_request_interval_seconds:
            time.sleep(self.min_request_interval_seconds - elapsed)
        self._last_request_at = time.monotonic()

    def _backoff(self, attempt: int) -> None:
        if self._pace_requests:
            time.sleep(self.min_request_interval_seconds * (attempt + 1))

    @staticmethod
    def _is_rate_limit_message(message: Any) -> bool:
        text = str(message).lower()
        return (
            "request" in text
            or "frequency" in text
            or "rate" in text
            or "spread" in text
            or "standard api" in text
            or "api key" in text
        )

    def fetch_company_financials(self, ticker: str) -> dict[str, Any]:
        symbol = ticker.strip().upper()
        if not symbol:
            raise AlphaVantageInvalidTicker("Ticker is required.")

        with self._lock:
            # 1. Active Memory Cache Check
            cached = self._cache.get(symbol)
            if cached:
                cache_time, cached_data = cached
                age = time.monotonic() - cache_time
                if age < CACHE_TTL_SECONDS:
                    logger.info("Serving company financials for %s from active memory cache (age=%.1fs)", symbol, age)
                    res = cached_data.copy()
                    res["_provenance"] = "CACHED"
                    res["provenance"] = cached_data["provenance"].copy()
                    res["provenance"]["source"] = "Alpha Vantage (Cached)"
                    res["provenance"]["provenance"] = "CACHED"
                    res["provenance"]["source_type"] = "CACHED"
                    res["provenance"]["notice"] = "Served from local provider memory cache."
                    return res
                elif self.is_circuit_breaker_active():
                    # Reuse stale cache if circuit breaker is open
                    logger.info("Serving company financials for %s from stale memory cache during circuit breaker active state", symbol)
                    res = cached_data.copy()
                    res["_provenance"] = "CACHED"
                    res["provenance"] = cached_data["provenance"].copy()
                    res["provenance"]["source"] = "Alpha Vantage (Cached Stale)"
                    res["provenance"]["provenance"] = "CACHED"
                    res["provenance"]["source_type"] = "CACHED"
                    res["provenance"]["notice"] = "Rate-limit circuit breaker active. Serving cached provider data."
                    return res

            # 2. Failure Cache Check
            failed = self._failure_cache.get(symbol)
            if failed:
                ttl = 300 if failed[1] is AlphaVantageInvalidTicker else 15
                if time.monotonic() - failed[0] < ttl:
                    logger.info("Serving cached failure for %s (%s)", symbol, failed[2])
                    raise failed[1](failed[2])

            # 3. Circuit Breaker Check before Network Requests
            if self.is_circuit_breaker_active():
                remaining = self._circuit_breaker_tripped_until - time.monotonic()
                raise AlphaVantageRateLimited(
                    f"Alpha Vantage rate-limit circuit breaker active ({remaining:.1f}s cooldown remaining)."
                )

            # 4. Outbound Provider Requests
            try:
                overview = self._request("OVERVIEW", symbol)
                if not isinstance(overview, dict) or not overview.get("Symbol"):
                    raise AlphaVantageInvalidTicker("Alpha Vantage did not return company overview data.")

                income = self._request("INCOME_STATEMENT", symbol)
                balance = self._request("BALANCE_SHEET", symbol)
                cash_flow = self._request("CASH_FLOW", symbol)

                quote: dict[str, Any] = {}
                unavailable_datasets: list[str] = []

                try:
                    quote = self._request("GLOBAL_QUOTE", symbol)
                except AlphaVantageError as exc:
                    logger.info("Optional dataset GLOBAL_QUOTE unavailable for %s: %s", symbol, exc)
                    unavailable_datasets.append("GLOBAL_QUOTE")

                result = normalize_alpha_vantage(symbol, overview, quote, income, balance, cash_flow)

                if unavailable_datasets:
                    result["provenance"]["unavailable_datasets"] = unavailable_datasets

                try:
                    result["historical_prices"] = self.fetch_daily_prices(symbol)
                    if "TIME_SERIES_DAILY" not in result["provenance"]["functions"]:
                        result["provenance"]["functions"].append("TIME_SERIES_DAILY")
                except AlphaVantageError as exc:
                    logger.info("Optional dataset TIME_SERIES_DAILY unavailable for %s: %s", symbol, exc)
                    result["historical_prices"] = []
                    result["provenance"].setdefault("unavailable_datasets", []).append("TIME_SERIES_DAILY")

            except AlphaVantageError as exc:
                self._failure_cache[symbol] = (time.monotonic(), type(exc), str(exc))
                raise

            self._cache[symbol] = (time.monotonic(), result)
            return result.copy()

    def fetch_daily_prices(self, ticker: str) -> list[dict[str, Any]]:
        """Optional normalized history for consumers that support a price chart."""
        payload = self._request("TIME_SERIES_DAILY", ticker.strip().upper())
        series = payload.get("Time Series (Daily)")
        if not isinstance(series, dict):
            raise AlphaVantageUnavailable("Alpha Vantage did not return daily historical prices.")
        rows: list[dict[str, Any]] = []
        for day, values in series.items():
            if isinstance(values, dict):
                rows.append({"date": day, "close": _number(values.get("4. close")), "volume": _number(values.get("5. volume"))})
        return rows


def normalize_alpha_vantage(
    ticker: str,
    overview: dict[str, Any],
    quote: dict[str, Any],
    income: dict[str, Any],
    balance: dict[str, Any],
    cash_flow: dict[str, Any],
) -> dict[str, Any]:
    """Map provider payloads to the pre-existing ValuEngine financial schema."""
    income_report, balance_report, cash_report = _first_report(income), _first_report(balance), _first_report(cash_flow)
    quote_data = quote.get("Global Quote") if isinstance(quote.get("Global Quote"), dict) else {}

    short_debt = _number(balance_report.get("shortTermDebt"))
    long_debt = _number(balance_report.get("longTermDebt"))
    reported_total_debt = _number(balance_report.get("shortLongTermDebtTotal"))
    total_debt = (
        reported_total_debt
        if reported_total_debt is not None
        else (short_debt + long_debt if short_debt is not None and long_debt is not None else None)
    )

    d_and_a = (
        _number(cash_report.get("depreciationDepletionAndAmortization"))
        if _number(cash_report.get("depreciationDepletionAndAmortization")) is not None
        else _number(income_report.get("depreciation"))
    )
    ebit = _number(income_report.get("operatingIncome"))
    reported_ebitda = _number(income_report.get("ebitda"))
    ebitda = reported_ebitda if reported_ebitda is not None else (ebit + d_and_a if ebit is not None and d_and_a is not None else None)

    market_cap = _number(overview.get("MarketCapitalization"))
    shares = _number(overview.get("SharesOutstanding"))

    quote_price = _number(quote_data.get("05. price"))
    derived_price = (market_cap / shares) if (quote_price is None and market_cap is not None and shares is not None and shares > 0) else None
    current_price = quote_price if quote_price is not None else derived_price

    period = (
        income_report.get("fiscalDateEnding")
        or balance_report.get("fiscalDateEnding")
        or cash_report.get("fiscalDateEnding")
        or "UNAVAILABLE"
    )
    retrieved_at = datetime.now(timezone.utc).isoformat()

    derived_fields: list[str] = []
    if reported_ebitda is None and ebitda is not None:
        derived_fields.append("ebitda")
    if quote_price is None and derived_price is not None:
        derived_fields.append("current_price")

    functions = ["OVERVIEW", "INCOME_STATEMENT", "BALANCE_SHEET", "CASH_FLOW"]
    if quote_price is not None:
        functions.append("GLOBAL_QUOTE")

    result: dict[str, Any] = {
        "ticker": ticker,
        "company_name": overview.get("Name") or None,
        "exchange": overview.get("Exchange") or None,
        "sector": overview.get("Sector") or None,
        "industry": overview.get("Industry") or None,
        "currency": overview.get("Currency") or None,
        "current_price": current_price,
        "market_cap": market_cap,
        "shares_outstanding": shares,
        "revenue": _number(income_report.get("totalRevenue")),
        "ebitda": ebitda,
        "ebit": ebit,
        "net_income": _number(income_report.get("netIncome")),
        "eps": _number(income_report.get("reportedEPS")),
        "operating_cash_flow": _number(cash_report.get("operatingCashflow")),
        "capex": _outflow(cash_report.get("capitalExpenditures")),
        "d_and_a": d_and_a,
        "total_debt": total_debt,
        "cash_and_equivalents": _number(balance_report.get("cashAndCashEquivalentsAtCarryingValue")),
        "book_equity": _number(balance_report.get("totalShareholderEquity")),
        "total_assets": _number(balance_report.get("totalAssets")),
        "total_liabilities": _number(balance_report.get("totalLiabilities")),
        "beta": _number(overview.get("Beta")),
        "historical_prices": [],
        "provenance": {
            "source": "Alpha Vantage",
            "provenance": "LIVE",
            "source_type": "LIVE",
            "source_name": "Alpha Vantage",
            "provider": "Alpha Vantage",
            "ticker": ticker,
            "period": period,
            "currency": overview.get("Currency") or None,
            "retrieved_at": retrieved_at,
            "functions": functions,
            "derived_fields": derived_fields,
        },
        "_provenance": "LIVE",
    }
    return result
