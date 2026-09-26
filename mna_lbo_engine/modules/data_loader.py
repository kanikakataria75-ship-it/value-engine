"""Company data access with explicit provenance.

Modes:
  local  - the local SQLite store only (no network).
  live   - Alpha Vantage first; on any provider failure the local copy is served and labelled
           LOCAL_FALLBACK with the provider's error. No fabricated or preset data is ever returned.
"""
from __future__ import annotations

import logging
from typing import Any

from .alpha_vantage_provider import AlphaVantageError, AlphaVantageProvider, AlphaVantageRateLimited
from .common import reconcile_ebitda
from .local_financial_store import LocalFinancialStore, get_default_store

logger = logging.getLogger(__name__)


class FinancialDataLoader:
    def __init__(self, provider: AlphaVantageProvider | None = None, store: LocalFinancialStore | None = None) -> None:
        self.provider = provider or AlphaVantageProvider()
        self._store = store

    @property
    def store(self) -> LocalFinancialStore:
        return self._store or get_default_store()

    def fetch_company(self, ticker: str, data_mode: str = "local") -> tuple[dict[str, Any] | None, str, str | None]:
        """Return (company, status, notice). status is LOCAL | LIVE | CACHED | LOCAL_FALLBACK | RATE_LIMITED | UNAVAILABLE."""
        symbol = str(ticker).strip().upper()
        if not symbol:
            return None, "UNAVAILABLE", "Ticker is required."
        if data_mode != "live":
            company = self.store.get_company(symbol)
            if company is None:
                return None, "UNAVAILABLE", f"{symbol} is not in the local dataset."
            return company, "LOCAL", None

        try:
            live = self.provider.fetch_company_financials(symbol)
        except AlphaVantageError as exc:
            local = self.store.get_company(symbol)
            status = "RATE_LIMITED" if isinstance(exc, AlphaVantageRateLimited) else "LOCAL_FALLBACK"
            if local is None:
                return None, "UNAVAILABLE", f"Live provider failed ({exc}) and {symbol} is not in the local dataset."
            local["provenance"]["notice"] = f"Live provider unavailable ({exc}); serving the local snapshot."
            local["provenance"]["source_type"] = status
            return local, status, str(exc)

        ebitda, derived = reconcile_ebitda(live.get("ebitda"), live.get("ebit"), live.get("d_and_a"))
        if derived:
            live["ebitda"] = ebitda
            live.setdefault("provenance", {}).setdefault("derived_fields", []).append("ebitda (EBIT + D&A)")
        try:
            # Keep the local sector taxonomy (Alpha Vantage uses different sector names) and do not persist
            # Alpha Vantage's unadjusted daily closes over the split/dividend-adjusted local series.
            has_prices = bool(self.store.get_daily_prices(symbol, limit=1))
            prices = [] if has_prices else live.get("historical_prices") or []
            self.store.save_company({**live, "historical_prices": prices}, preserve_classification=True)
        except Exception as exc:  # persistence must not break a live read
            logger.warning("Failed to persist %s to the local store: %s", symbol, exc)
        stored = self.store.get_company(symbol) or live
        status = "CACHED" if (live.get("provenance") or {}).get("source_type") == "CACHED" else "LIVE"
        stored["provenance"] = {**(live.get("provenance") or {}), "source_type": status,
                                "period_end": stored.get("period"), "period_type": "FY"}
        return stored, status, None
