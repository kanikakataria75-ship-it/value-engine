"""Abstract Market Data Provider interface and Mock implementation.

Defines the contract for external/paid market data sources, decoupling ingestion
from any specific third-party API.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MarketDataProvider(ABC):
    """Abstract base class for financial market data providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the unique identifier/name of the provider."""
        raise NotImplementedError

    @abstractmethod
    def get_company_profile(self, ticker: str) -> dict[str, Any]:
        """
        Fetch company profile / overview metadata.
        Expected keys: name, exchange, sector, industry, currency, shares_outstanding, beta, market_cap.
        """
        raise NotImplementedError

    @abstractmethod
    def get_quote(self, ticker: str) -> dict[str, Any]:
        """
        Fetch current market price quote.
        Expected keys: price, volume, timestamp.
        """
        raise NotImplementedError

    @abstractmethod
    def get_income_statement(self, ticker: str) -> dict[str, Any]:
        """
        Fetch the latest annual/LTM income statement.
        Expected keys: period, revenue, ebitda, ebit, net_income, eps, depreciation.
        """
        raise NotImplementedError

    @abstractmethod
    def get_balance_sheet(self, ticker: str) -> dict[str, Any]:
        """
        Fetch the latest balance sheet snapshot.
        Expected keys: period, total_debt, short_term_debt, long_term_debt, cash_and_equivalents,
                       book_equity, total_assets, total_liabilities.
        """
        raise NotImplementedError

    @abstractmethod
    def get_cash_flow(self, ticker: str) -> dict[str, Any]:
        """
        Fetch the latest cash flow statement.
        Expected keys: period, operating_cash_flow, capex, depreciation_amortization.
        """
        raise NotImplementedError

    @abstractmethod
    def get_historical_prices(self, ticker: str, limit: int = 250) -> list[dict[str, Any]]:
        """
        Fetch daily historical price series.
        Expected list of dicts with: date (YYYY-MM-DD), open, high, low, close, volume.
        """
        raise NotImplementedError


class MockMarketDataProvider(MarketDataProvider):
    """Configurable mock provider for testing and validation without network requests."""

    def __init__(
        self,
        name: str = "MockProvider",
        responses: dict[str, dict[str, Any]] | None = None,
        default_price_count: int = 250,
    ) -> None:
        self._name = name
        self.responses = responses or {}
        self.default_price_count = default_price_count
        self.calls: list[tuple[str, str]] = []

    @property
    def provider_name(self) -> str:
        return self._name

    def _get_field(self, ticker: str, endpoint: str, default: Any) -> Any:
        self.calls.append((ticker, endpoint))
        ticker_data = self.responses.get(ticker.upper(), {})
        return ticker_data.get(endpoint, default)

    def get_company_profile(self, ticker: str) -> dict[str, Any]:
        default = {
            "name": f"{ticker.upper()} Inc.",
            "exchange": "NASDAQ",
            "sector": "Information Technology",
            "industry": "Software",
            "currency": "USD",
            "shares_outstanding": 10000000.0,
            "beta": 1.1,
            "market_cap": 1500000000.0,
        }
        return self._get_field(ticker, "profile", default)

    def get_quote(self, ticker: str) -> dict[str, Any]:
        default = {"price": 150.0, "volume": 1000000.0}
        return self._get_field(ticker, "quote", default)

    def get_income_statement(self, ticker: str) -> dict[str, Any]:
        default = {
            "period": "2024-12-31",
            "revenue": 500000000.0,
            "ebitda": 150000000.0,
            "ebit": 120000000.0,
            "net_income": 90000000.0,
            "eps": 9.0,
            "depreciation": 30000000.0,
        }
        return self._get_field(ticker, "income_statement", default)

    def get_balance_sheet(self, ticker: str) -> dict[str, Any]:
        default = {
            "period": "2024-12-31",
            "total_debt": 50000000.0,
            "short_term_debt": 10000000.0,
            "long_term_debt": 40000000.0,
            "cash_and_equivalents": 40000000.0,
            "book_equity": 200000000.0,
            "total_assets": 300000000.0,
            "total_liabilities": 100000000.0,
        }
        return self._get_field(ticker, "balance_sheet", default)

    def get_cash_flow(self, ticker: str) -> dict[str, Any]:
        default = {
            "period": "2024-12-31",
            "operating_cash_flow": 130000000.0,
            "capex": 25000000.0,
            "depreciation_amortization": 30000000.0,
        }
        return self._get_field(ticker, "cash_flow", default)

    def get_historical_prices(self, ticker: str, limit: int = 250) -> list[dict[str, Any]]:
        self.calls.append((ticker, "historical_prices"))
        ticker_data = self.responses.get(ticker.upper(), {})
        if "historical_prices" in ticker_data:
            return ticker_data["historical_prices"]

        count = min(limit, self.default_price_count)
        return [
            {
                "date": f"2024-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}",
                "open": 100.0 + i * 0.2,
                "high": 102.0 + i * 0.2,
                "low": 99.0 + i * 0.2,
                "close": 100.0 + i * 0.2,
                "volume": 1000000.0 + i * 100,
            }
            for i in range(count)
        ]
