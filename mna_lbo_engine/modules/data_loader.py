"""Financial Data Ingestion & Provenance Engine.

Manages data retrieval with LocalFinancialStore precedence and Alpha Vantage fallback.
"""
from __future__ import annotations

import datetime
import logging
from typing import Any, Dict

from .alpha_vantage_provider import AlphaVantageProvider
from .local_financial_store import LocalFinancialStore, get_default_store

logger = logging.getLogger(__name__)


class FinancialDataLoader:
    def __init__(
        self,
        provider: AlphaVantageProvider | None = None,
        store: LocalFinancialStore | None = None,
    ) -> None:
        self.provider = provider or AlphaVantageProvider()
        self.store = store or get_default_store()

    def fetch_company_financials(self, ticker: str, data_mode: str = "auto") -> Dict[str, Any] | None:
        """
        Fetch and normalize company financials.
        - data_mode == 'local': query LocalFinancialStore strictly. If absent, return None (no external network).
        - data_mode == 'live': query external provider (save to LocalFinancialStore on success).
        - data_mode == 'auto' (default): check LocalFinancialStore first; if absent, query external provider.
        """
        symbol = str(ticker).strip().upper()
        if not symbol:
            return None if data_mode == "local" else self.provider.fetch_company_financials(ticker)

        if data_mode == "local":
            # 1. Strictly query local SQLite store
            local_data = self.store.get_company(symbol)
            if local_data is not None:
                logger.info("Retrieved %s from LocalFinancialStore in local mode", symbol)
                return local_data
            logger.info("Ticker %s not present in LocalFinancialStore in local mode", symbol)
            return None

        if data_mode == "auto":
            local_data = self.store.get_company(symbol)
            if local_data is not None:
                logger.info("Retrieved %s from LocalFinancialStore (auto mode)", symbol)
                return local_data

        # 2. In 'live' or auto-with-local-miss mode, query external provider
        logger.info("Querying external provider for %s", symbol)
        live_result = self.provider.fetch_company_financials(symbol)

        # 3. Save successfully retrieved data to LocalFinancialStore
        try:
            self.store.save_company(live_result)
            logger.info("Persisted %s to LocalFinancialStore", symbol)
        except Exception as exc:
            logger.warning("Failed to persist %s to LocalFinancialStore: %s", symbol, exc)

        return live_result

    def apply_provenance(self, data: Dict[str, Any], source: str = "DEMO") -> Dict[str, Any]:
        """
        Standardized provenance schema.
        """
        data["_provenance"] = source
        data["provenance_metadata"] = {
            "source_type": source,
            "source_name": "ValuEngine Preset",
            "retrieved_at": datetime.datetime.now().isoformat(),
            "period": "LTM",
            "currency": data.get("currency", "USD"),
            "units": "Absolute",
        }
        return data
