"""Bulk Data Ingestion Framework for ValuEngine Local Database.

Orchestrates reading company universe, querying market data provider, normalizing
to the locked ValuEngine financial schema, validating quality rules, and persisting
into LocalFinancialStore with resume/retry tracking.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Callable

from .local_financial_store import LocalFinancialStore, get_default_store
from .market_data_provider import MarketDataProvider

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UNIVERSE_CSV = PROJECT_ROOT / "data" / "company_universe.csv"
DEFAULT_SUCCESS_CSV = PROJECT_ROOT / "data" / "ingestion_success.csv"
DEFAULT_FAILURES_CSV = PROJECT_ROOT / "data" / "ingestion_failures.csv"

MIN_REQUIRED_PRICE_RECORDS = 200


class ValidationError(ValueError):
    """Raised when provider payload fails financial quality gates."""


def _number(value: Any) -> float | None:
    if value is None or value == "" or value == "None":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class BulkDataIngestor:
    """Provider-agnostic bulk financial data ingestion and validation engine."""

    def __init__(
        self,
        provider: MarketDataProvider,
        store: LocalFinancialStore | None = None,
        universe_csv: Path | str = DEFAULT_UNIVERSE_CSV,
        success_csv: Path | str = DEFAULT_SUCCESS_CSV,
        failures_csv: Path | str = DEFAULT_FAILURES_CSV,
    ) -> None:
        self.provider = provider
        self.store = store or get_default_store()
        self.universe_csv = Path(universe_csv)
        self.success_csv = Path(success_csv)
        self.failures_csv = Path(failures_csv)
        self._ensure_output_files()

    def _ensure_output_files(self) -> None:
        self.success_csv.parent.mkdir(parents=True, exist_ok=True)
        self.failures_csv.parent.mkdir(parents=True, exist_ok=True)

        if not self.success_csv.exists():
            with open(self.success_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "ticker", "company_name", "exchange", "country",
                    "currency", "sector", "industry", "price_records",
                    "provider", "ingested_at"
                ])

        if not self.failures_csv.exists():
            with open(self.failures_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "ticker", "company_name", "error_type", "reason",
                    "provider", "attempted_at"
                ])

    def get_successful_tickers(self) -> set[str]:
        """Read existing successful ingestion log for resume support."""
        if not self.success_csv.exists():
            return set()
        successful = set()
        with open(self.success_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ticker = (row.get("ticker") or "").strip().upper()
                if ticker:
                    successful.add(ticker)
        return successful

    def normalize_and_validate(
        self,
        universe_row: dict[str, str],
        profile: dict[str, Any],
        quote: dict[str, Any],
        income: dict[str, Any],
        balance: dict[str, Any],
        cash_flow: dict[str, Any],
        prices: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Map raw provider components to the locked ValuEngine financial schema and validate."""
        ticker = universe_row.get("ticker", "").strip().upper()
        if not ticker:
            raise ValidationError("Ticker is required.")

        company_name = profile.get("name") or universe_row.get("company_name") or None
        if not company_name:
            raise ValidationError("company_name is required and cannot be empty.")

        exchange = profile.get("exchange") or universe_row.get("exchange") or "UNKNOWN"
        sector = profile.get("sector") or universe_row.get("sector") or "UNKNOWN"
        industry = profile.get("industry") or universe_row.get("industry") or "UNKNOWN"
        currency = profile.get("currency") or universe_row.get("currency") or "USD"

        # Price and Market Cap
        current_price = _number(quote.get("price")) or _number(quote.get("close"))
        if current_price is None or current_price <= 0:
            raise ValidationError(f"current_price must be strictly positive. Got: {current_price}")

        shares = _number(profile.get("shares_outstanding"))
        if shares is None or shares <= 0:
            raise ValidationError(f"shares_outstanding must be strictly positive. Got: {shares}")

        market_cap = _number(profile.get("market_cap")) or (current_price * shares)

        # Financial Statements
        revenue = _number(income.get("revenue"))
        if revenue is None or revenue <= 0:
            raise ValidationError(f"revenue must be strictly positive for standard valuation. Got: {revenue}")

        ebit = _number(income.get("ebit"))
        if ebit is None:
            raise ValidationError("ebit is required and cannot be None.")

        net_income = _number(income.get("net_income"))
        if net_income is None:
            raise ValidationError("net_income is required and cannot be None.")

        eps = _number(income.get("eps"))
        operating_cash_flow = _number(cash_flow.get("operating_cash_flow"))

        capex = _number(cash_flow.get("capex"))
        if capex is None:
            raise ValidationError("capex is required and cannot be None.")
        capex = abs(capex)  # Normalize to positive outflow convention

        d_and_a = _number(cash_flow.get("depreciation_amortization")) or _number(income.get("depreciation")) or 0.0
        reported_ebitda = _number(income.get("ebitda"))
        ebitda = reported_ebitda if reported_ebitda is not None else (ebit + d_and_a)

        # Balance Sheet
        total_debt = _number(balance.get("total_debt"))
        if total_debt is None:
            short_debt = _number(balance.get("short_term_debt")) or 0.0
            long_debt = _number(balance.get("long_term_debt")) or 0.0
            total_debt = short_debt + long_debt

        if total_debt is None or total_debt < 0:
            raise ValidationError(f"total_debt cannot be None or negative. Got: {total_debt}")

        cash_and_eq = _number(balance.get("cash_and_equivalents"))
        if cash_and_eq is None or cash_and_eq < 0:
            raise ValidationError(f"cash_and_equivalents cannot be None or negative. Got: {cash_and_eq}")

        book_equity = _number(balance.get("book_equity"))
        if book_equity is None:
            raise ValidationError("book_equity is required for Invested Capital / ROIC diagnostics.")

        total_assets = _number(balance.get("total_assets"))
        total_liabilities = _number(balance.get("total_liabilities"))

        beta = _number(profile.get("beta"))
        if beta is None:
            raise ValidationError("beta is required for CAPM discount rate estimation.")

        # Historical Prices validation
        if not isinstance(prices, list) or len(prices) < MIN_REQUIRED_PRICE_RECORDS:
            price_count = len(prices) if isinstance(prices, list) else 0
            raise ValidationError(
                f"historical_prices must contain at least {MIN_REQUIRED_PRICE_RECORDS} daily records for Risk Lab. Got: {price_count}"
            )

        period = income.get("period") or balance.get("period") or cash_flow.get("period") or "LTM"
        retrieved_at = datetime.now(timezone.utc).isoformat()

        provenance = {
            "source": self.provider.provider_name,
            "provenance": "LIVE",
            "source_type": "LIVE",
            "source_name": f"{self.provider.provider_name} Bulk Ingest",
            "provider": self.provider.provider_name,
            "ticker": ticker,
            "period": period,
            "currency": currency,
            "retrieved_at": retrieved_at,
            "price_records_count": len(prices),
        }

        return {
            "ticker": ticker,
            "company_name": company_name,
            "exchange": exchange,
            "sector": sector,
            "industry": industry,
            "currency": currency,
            "current_price": current_price,
            "market_cap": market_cap,
            "shares_outstanding": shares,
            "revenue": revenue,
            "ebitda": ebitda,
            "ebit": ebit,
            "net_income": net_income,
            "eps": eps,
            "operating_cash_flow": operating_cash_flow,
            "capex": capex,
            "d_and_a": d_and_a,
            "total_debt": total_debt,
            "cash_and_equivalents": cash_and_eq,
            "book_equity": book_equity,
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "beta": beta,
            "historical_prices": prices,
            "period": period,
            "retrieved_at": retrieved_at,
            "provenance": provenance,
            "_provenance": "LIVE",
        }

    def _log_success(self, normalized: dict[str, Any], country: str = "USA") -> None:
        with open(self.success_csv, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                normalized["ticker"],
                normalized["company_name"],
                normalized["exchange"],
                country,
                normalized["currency"],
                normalized["sector"],
                normalized["industry"],
                len(normalized.get("historical_prices", [])),
                self.provider.provider_name,
                normalized["retrieved_at"],
            ])

    def _log_failure(self, ticker: str, company_name: str, error_type: str, reason: str) -> None:
        with open(self.failures_csv, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                ticker,
                company_name,
                error_type,
                reason,
                self.provider.provider_name,
                datetime.now(timezone.utc).isoformat(),
            ])

    def ingest_company(
        self,
        universe_row: dict[str, str],
        overwrite: bool = False,
    ) -> tuple[bool, str]:
        """Ingest a single company with validation, SQLite persistence, and outcome logging."""
        ticker = (universe_row.get("ticker") or "").strip().upper()
        company_name = universe_row.get("company_name", ticker)
        country = universe_row.get("country", "USA")

        if not ticker:
            return False, "EMPTY_TICKER"

        # Check resume condition: skip if already in DB or success log (unless overwrite=True)
        if not overwrite:
            existing = self.store.get_company(ticker, include_prices=False)
            if existing is not None:
                return True, "SKIPPED_ALREADY_EXISTS"

        try:
            profile = self.provider.get_company_profile(ticker)
            quote = self.provider.get_quote(ticker)
            income = self.provider.get_income_statement(ticker)
            balance = self.provider.get_balance_sheet(ticker)
            cash_flow = self.provider.get_cash_flow(ticker)
            prices = self.provider.get_historical_prices(ticker, limit=250)

            normalized = self.normalize_and_validate(
                universe_row=universe_row,
                profile=profile,
                quote=quote,
                income=income,
                balance=balance,
                cash_flow=cash_flow,
                prices=prices,
            )

            # Persist to SQLite store
            self.store.save_company(normalized)
            self._log_success(normalized, country=country)
            return True, "SUCCESS"

        except ValidationError as exc:
            reason = str(exc)
            logger.warning("Validation failed for %s: %s", ticker, reason)
            self._log_failure(ticker, company_name, "VALIDATION_ERROR", reason)
            return False, reason
        except Exception as exc:
            reason = f"{type(exc).__name__}: {str(exc)}"
            logger.error("Provider/Transport error for %s: %s", ticker, reason)
            self._log_failure(ticker, company_name, "PROVIDER_ERROR", reason)
            return False, reason

    def ingest_universe(
        self,
        limit: int | None = None,
        ticker_list: list[str] | None = None,
        overwrite: bool = False,
        progress_callback: Callable[[int, int, str, str], None] | None = None,
    ) -> dict[str, Any]:
        """Run bulk ingestion across the company universe (optionally filtered by ticker_list or limit)."""
        if not self.universe_csv.exists():
            raise FileNotFoundError(f"Universe CSV not found at: {self.universe_csv}")

        rows: list[dict[str, str]] = []
        with open(self.universe_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

        if ticker_list:
            filter_set = {t.strip().upper() for t in ticker_list if t.strip()}
            rows = [r for r in rows if (r.get("ticker") or "").strip().upper() in filter_set]

        if limit is not None and limit > 0:
            rows = rows[:limit]

        total = len(rows)
        successful = 0
        skipped = 0
        failed = 0

        for index, row in enumerate(rows, start=1):
            ticker = (row.get("ticker") or "").strip().upper()
            success, status = self.ingest_company(row, overwrite=overwrite)

            if success:
                if status == "SKIPPED_ALREADY_EXISTS":
                    skipped += 1
                else:
                    successful += 1
            else:
                failed += 1

            if progress_callback:
                progress_callback(index, total, ticker, status)

        return {
            "total_processed": total,
            "successful": successful,
            "skipped": skipped,
            "failed": failed,
            "success_rate": f"{(successful + skipped) / total * 100:.1f}%" if total > 0 else "0.0%",
            "db_company_count": self.store.get_company_count(),
        }
