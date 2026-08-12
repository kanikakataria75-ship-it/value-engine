"""
Financial Data Ingestion & Provenance Engine.
"""

from typing import Dict, Any
import datetime

from .alpha_vantage_provider import AlphaVantageProvider

class FinancialDataLoader:
    def __init__(self, provider: AlphaVantageProvider | None = None) -> None:
        self.provider = provider or AlphaVantageProvider()

    def fetch_company_financials(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch and normalize live company financials through the sole provider.
        Provider errors are raised to the caller, which can make an explicit,
        provenance-labelled demonstration fallback decision.
        """
        return self.provider.fetch_company_financials(ticker)

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
            "units": "Absolute"
        }
        return data
