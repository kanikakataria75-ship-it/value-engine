"""Bulk data ingestion for the local store.

Reads the company universe, pulls data from a MarketDataProvider, normalises it to the ValuEngine
schema, runs the same data-quality rules the API applies at serving time, and persists companies
that pass. Every derived value is recorded in the provenance block; nothing is silently defaulted.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Callable

from .common import is_balance_sheet_financial, reconcile_ebitda, to_float
from .data_quality_engine import run_data_quality_checks
from .local_financial_store import LocalFinancialStore, get_default_store, normalize_sector
from .market_data_provider import MarketDataProvider

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UNIVERSE_CSV = PROJECT_ROOT / "data" / "company_universe.csv"
DEFAULT_SUCCESS_CSV = PROJECT_ROOT / "data" / "ingestion_success.csv"
DEFAULT_FAILURES_CSV = PROJECT_ROOT / "data" / "ingestion_failures.csv"

MIN_REQUIRED_PRICE_RECORDS = 200


class ValidationError(ValueError):
    """Raised when provider data fails the ingestion quality gates."""


class BulkDataIngestor:
    def __init__(self, provider: MarketDataProvider, store: LocalFinancialStore | None = None,
                 universe_csv: Path | str = DEFAULT_UNIVERSE_CSV, success_csv: Path | str = DEFAULT_SUCCESS_CSV,
                 failures_csv: Path | str = DEFAULT_FAILURES_CSV) -> None:
        self.provider = provider
        self.store = store or get_default_store()
        self.universe_csv = Path(universe_csv)
        self.success_csv = Path(success_csv)
        self.failures_csv = Path(failures_csv)
        self._ensure_output_files()

    def _ensure_output_files(self) -> None:
        for path, header in (
            (self.success_csv, ["ticker", "company_name", "exchange", "country", "currency", "sector", "industry",
                                "price_records", "provider", "ingested_at"]),
            (self.failures_csv, ["ticker", "company_name", "error_type", "reason", "provider", "attempted_at"]),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                with open(path, "w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow(header)

    def get_successful_tickers(self) -> set[str]:
        if not self.success_csv.exists():
            return set()
        with open(self.success_csv, "r", encoding="utf-8") as f:
            return {(row.get("ticker") or "").strip().upper() for row in csv.DictReader(f) if row.get("ticker")}

    def normalize_and_validate(self, universe_row: dict[str, str], profile: dict[str, Any], quote: dict[str, Any],
                               income: dict[str, Any], balance: dict[str, Any], cash_flow: dict[str, Any],
                               prices: list[dict[str, Any]], conversion: dict[str, Any] | None = None,
                               history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        ticker = (universe_row.get("ticker") or "").strip().upper()
        if not ticker:
            raise ValidationError("Ticker is required.")
        company_name = profile.get("name") or universe_row.get("company_name")
        if not company_name:
            raise ValidationError("company_name is required.")
        derived: list[str] = []

        price = to_float(quote.get("price")) or to_float(quote.get("close"))
        if price is None or price <= 0:
            raise ValidationError(f"current_price must be strictly positive. Got: {price}")
        shares = to_float(profile.get("shares_outstanding"))
        if shares is None or shares <= 0:
            raise ValidationError(f"shares_outstanding must be strictly positive. Got: {shares}")
        market_cap = to_float(profile.get("market_cap"))
        if market_cap is None:
            market_cap = price * shares
            derived.append("market_cap (price x shares)")

        revenue = to_float(income.get("revenue"))
        if revenue is None or revenue <= 0:
            raise ValidationError(f"revenue must be strictly positive. Got: {revenue}")
        ebit = to_float(income.get("ebit"))
        if ebit is None:
            raise ValidationError("Operating income (EBIT) is not reported.")
        if income.get("ebit_source") and income["ebit_source"] != "Operating Income":
            derived.append(f"ebit ({income['ebit_source']})")
        net_income = to_float(income.get("net_income"))
        if net_income is None:
            raise ValidationError("net_income is not reported.")

        d_and_a = to_float(cash_flow.get("depreciation_amortization"))
        if d_and_a is None:
            d_and_a = to_float(income.get("depreciation"))
        ebitda, ebitda_derived = reconcile_ebitda(income.get("ebitda"), ebit, d_and_a)
        if ebitda_derived:
            derived.append("ebitda (EBIT + D&A)")

        total_debt = to_float(balance.get("total_debt"))
        if total_debt is None:
            total_debt = 0.0
            derived.append("total_debt (no debt lines reported; set to 0)")
        cash = to_float(balance.get("cash_and_equivalents"))
        if cash is None:
            raise ValidationError("cash_and_equivalents is not reported.")
        book_equity = to_float(balance.get("book_equity"))
        if book_equity is None:
            raise ValidationError("book_equity is not reported.")

        company = {
            "ticker": ticker,
            "company_name": company_name,
            "exchange": profile.get("exchange") or universe_row.get("exchange"),
            "sector": normalize_sector(profile.get("sector") or universe_row.get("sector")),
            "industry": profile.get("industry") or universe_row.get("industry"),
            "currency": (profile.get("currency") or universe_row.get("currency") or "USD").upper(),
            "current_price": price, "market_cap": market_cap, "shares_outstanding": shares,
            "revenue": revenue, "ebitda": ebitda, "ebit": ebit, "net_income": net_income,
            "eps": to_float(income.get("eps")), "operating_cash_flow": to_float(cash_flow.get("operating_cash_flow")),
            "capex": to_float(cash_flow.get("capex")), "d_and_a": d_and_a, "total_debt": total_debt,
            "cash_and_equivalents": cash, "book_equity": book_equity,
            "total_assets": to_float(balance.get("total_assets")), "total_liabilities": to_float(balance.get("total_liabilities")),
            "beta": to_float(profile.get("beta")),
            "historical_prices": prices,
        }
        if company["capex"] is None and not is_balance_sheet_financial(company):
            prior = next((row for row in reversed(history or [])
                          if to_float(row.get("capex")) is not None and to_float(row.get("revenue"))), None)
            if prior is None:
                raise ValidationError("capex is not reported (required for the DCF of an operating company).")
            company["capex"] = revenue * to_float(prior["capex"]) / to_float(prior["revenue"])
            derived.append(f"capex (estimated from the {prior['period_end']} capex/revenue ratio)")
        if not isinstance(prices, list) or len(prices) < MIN_REQUIRED_PRICE_RECORDS:
            raise ValidationError(f"historical_prices must contain at least {MIN_REQUIRED_PRICE_RECORDS} daily records. "
                                  f"Got: {len(prices) if isinstance(prices, list) else 0}")

        period = income.get("period") or balance.get("period") or cash_flow.get("period")
        retrieved_at = datetime.now(timezone.utc).isoformat()
        company.update({
            "period": period,
            "retrieved_at": retrieved_at,
            "provenance": {
                "source": self.provider.provider_name, "provider": self.provider.provider_name,
                "source_type": "INGESTED", "ticker": ticker, "period_end": period, "period_type": "FY",
                "currency": company["currency"], "retrieved_at": retrieved_at, "price_records_count": len(prices),
                "derived_fields": derived, "statement_conversion": conversion,
            },
        })
        errors = [i for i in run_data_quality_checks(company) if i["severity"] == "ERROR"]
        if errors:
            raise ValidationError("; ".join(i["message"] for i in errors))
        return company

    def _log(self, path: Path, row: list[Any]) -> None:
        with open(path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)

    def ingest_company(self, universe_row: dict[str, str], overwrite: bool = False) -> tuple[bool, str]:
        ticker = (universe_row.get("ticker") or "").strip().upper()
        company_name = universe_row.get("company_name", ticker)
        if not ticker:
            return False, "EMPTY_TICKER"
        if not overwrite and self.store.get_company(ticker, include_prices=False) is not None:
            return True, "SKIPPED_ALREADY_EXISTS"
        now = datetime.now(timezone.utc).isoformat()
        try:
            history_fn = getattr(self.provider, "get_annual_history", None)
            history = history_fn(ticker) if callable(history_fn) else []
            conversion_fn = getattr(self.provider, "statement_conversion", None)
            normalized = self.normalize_and_validate(
                universe_row=universe_row,
                profile=self.provider.get_company_profile(ticker),
                quote=self.provider.get_quote(ticker),
                income=self.provider.get_income_statement(ticker),
                balance=self.provider.get_balance_sheet(ticker),
                cash_flow=self.provider.get_cash_flow(ticker),
                prices=self.provider.get_historical_prices(ticker, limit=250),
                conversion=conversion_fn(ticker) if callable(conversion_fn) else None,
                history=history,
            )
            normalized["fundamentals_history"] = history
            self.store.save_company(normalized)
            self._log(self.success_csv, [ticker, normalized["company_name"], normalized["exchange"],
                                         universe_row.get("country", ""), normalized["currency"], normalized["sector"],
                                         normalized["industry"], len(normalized["historical_prices"]),
                                         self.provider.provider_name, normalized["retrieved_at"]])
            return True, "SUCCESS"
        except ValidationError as exc:
            logger.warning("Validation failed for %s: %s", ticker, exc)
            self._log(self.failures_csv, [ticker, company_name, "VALIDATION_ERROR", str(exc), self.provider.provider_name, now])
            return False, str(exc)
        except Exception as exc:  # provider / transport errors are logged and the run continues
            reason = f"{type(exc).__name__}: {exc}"
            logger.error("Provider error for %s: %s", ticker, reason)
            self._log(self.failures_csv, [ticker, company_name, "PROVIDER_ERROR", reason, self.provider.provider_name, now])
            return False, reason

    def ingest_universe(self, limit: int | None = None, ticker_list: list[str] | None = None, overwrite: bool = False,
                        progress_callback: Callable[[int, int, str, str], None] | None = None) -> dict[str, Any]:
        if not self.universe_csv.exists():
            raise FileNotFoundError(f"Universe CSV not found at: {self.universe_csv}")
        with open(self.universe_csv, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if ticker_list:
            wanted = {t.strip().upper() for t in ticker_list if t.strip()}
            rows = [r for r in rows if (r.get("ticker") or "").strip().upper() in wanted]
        if limit:
            rows = rows[:limit]
        successful = skipped = failed = 0
        for index, row in enumerate(rows, start=1):
            ok, status = self.ingest_company(row, overwrite=overwrite)
            if ok and status == "SKIPPED_ALREADY_EXISTS":
                skipped += 1
            elif ok:
                successful += 1
            else:
                failed += 1
            if progress_callback:
                progress_callback(index, len(rows), (row.get("ticker") or "").upper(), status)
        total = len(rows)
        return {
            "total_processed": total, "successful": successful, "skipped": skipped, "failed": failed,
            "success_rate": f"{(successful + skipped) / total * 100:.1f}%" if total else "0.0%",
            "db_company_count": self.store.get_company_count(),
        }
