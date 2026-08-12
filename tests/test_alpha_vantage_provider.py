from __future__ import annotations

import pytest

from backend.services import valuation_service as service
from mna_lbo_engine.modules.alpha_vantage_provider import (
    AlphaVantageInvalidTicker,
    AlphaVantageProvider,
    AlphaVantageRateLimited,
    AlphaVantageUnavailable,
    normalize_alpha_vantage,
)


class MockResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError("provider failure")

    def json(self) -> dict:
        return self.payload


class MockSession:
    def __init__(self, payloads: dict[str, dict]) -> None:
        self.payloads = payloads
        self.calls: list[dict] = []

    def get(self, _url: str, *, params: dict, timeout: float):
        self.calls.append(params)
        func = params["function"]
        payload = self.payloads.get(func, {})
        return MockResponse(payload)


def provider_payloads(symbol: str) -> dict[str, dict]:
    return {
        "OVERVIEW": {
            "Symbol": symbol,
            "Name": f"{symbol} Example",
            "Exchange": "NASDAQ",
            "Sector": "Technology",
            "Industry": "Software",
            "Currency": "USD",
            "MarketCapitalization": "1000000",
            "SharesOutstanding": "10000",
            "Beta": "1.2",
        },
        "GLOBAL_QUOTE": {"Global Quote": {"05. price": "100.50"}},
        "INCOME_STATEMENT": {
            "annualReports": [
                {
                    "fiscalDateEnding": "2025-12-31",
                    "totalRevenue": "500000",
                    "ebitda": "150000",
                    "operatingIncome": "125000",
                    "netIncome": "100000",
                    "reportedEPS": "10.0",
                }
            ]
        },
        "BALANCE_SHEET": {
            "annualReports": [
                {
                    "cashAndCashEquivalentsAtCarryingValue": "50000",
                    "shortTermDebt": "10000",
                    "longTermDebt": "40000",
                    "totalShareholderEquity": "250000",
                    "totalAssets": "600000",
                    "totalLiabilities": "350000",
                }
            ]
        },
        "CASH_FLOW": {
            "annualReports": [
                {
                    "operatingCashflow": "125000",
                    "capitalExpenditures": "-20000",
                    "depreciationDepletionAndAmortization": "25000",
                }
            ]
        },
        "TIME_SERIES_DAILY": {
            "Time Series (Daily)": {"2025-12-31": {"4. close": "100.50", "5. volume": "12345"}}
        },
    }


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT"])
def test_provider_normalizes_successful_company_response_with_live_provenance(ticker):
    session = MockSession(provider_payloads(ticker))
    result = AlphaVantageProvider(api_key="TEST_ALPHA_VANTAGE_KEY", session=session).fetch_company_financials(ticker)
    assert result["ticker"] == ticker
    assert result["company_name"] == f"{ticker} Example"
    assert result["revenue"] == 500000.0
    assert result["ebitda"] == 150000.0
    assert result["capex"] == 20000.0
    assert result["total_debt"] == 50000.0
    assert result["provenance"]["source"] == "Alpha Vantage"
    assert result["provenance"]["provenance"] == "LIVE"
    assert result["_provenance"] == "LIVE"
    assert result["historical_prices"] == [{"date": "2025-12-31", "close": 100.5, "volume": 12345.0}]
    assert len(session.calls) == 6


def test_normalization_preserves_zero_and_missing_values_without_fabrication():
    payloads = provider_payloads("AAPL")
    payloads["GLOBAL_QUOTE"]["Global Quote"]["05. price"] = "0"
    del payloads["INCOME_STATEMENT"]["annualReports"][0]["ebitda"]
    result = normalize_alpha_vantage(
        "AAPL",
        payloads["OVERVIEW"],
        payloads["GLOBAL_QUOTE"],
        payloads["INCOME_STATEMENT"],
        payloads["BALANCE_SHEET"],
        payloads["CASH_FLOW"],
    )
    assert result["current_price"] == 0.0
    # EBITDA is derived from EBIT + D&A when reported value is absent (125000 + 25000)
    assert result["ebitda"] == 150000.0
    assert "ebitda" in result["provenance"]["derived_fields"]


def test_provider_caching_and_subsequent_request_provenance():
    session = MockSession(provider_payloads("AAPL"))
    provider = AlphaVantageProvider(api_key="TEST_ALPHA_VANTAGE_KEY", session=session)
    
    first = provider.fetch_company_financials("AAPL")
    assert first["_provenance"] == "LIVE"
    assert len(session.calls) == 6

    second = provider.fetch_company_financials("AAPL")
    assert second["_provenance"] == "CACHED"
    assert second["provenance"]["source_type"] == "CACHED"
    # No additional HTTP calls made
    assert len(session.calls) == 6


def test_rate_limit_trips_circuit_breaker_and_activates_cooldown():
    rate_limited = MockSession({"OVERVIEW": {"Note": "Standard API rate limit reached. Thank you for using Alpha Vantage!"}})
    provider = AlphaVantageProvider(api_key="TEST_ALPHA_VANTAGE_KEY", session=rate_limited)
    
    with pytest.raises(AlphaVantageRateLimited, match="rate limit reached"):
        provider.fetch_company_financials("AAPL")
    
    assert provider.is_circuit_breaker_active() is True
    
    # Next request immediately trips without calling HTTP session
    initial_calls = len(rate_limited.calls)
    with pytest.raises(AlphaVantageRateLimited, match="circuit breaker active"):
        provider.fetch_company_financials("MSFT")
    
    assert len(rate_limited.calls) == initial_calls


def test_api_company_handles_rate_limited_status_gracefully(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app

    class RateLimitedLoader:
        def fetch_company_financials(self, _ticker):
            raise AlphaVantageRateLimited("Alpha Vantage rate-limit circuit breaker active.")

    monkeypatch.setattr(service, "_data_loader", RateLimitedLoader())
    response = TestClient(app).get("/api/company/AAPL").json()
    assert response["status"] == "RATE_LIMITED"
    assert response["provenance"]["source"] == "RATE_LIMITED"
    assert "rate limited" in response["warnings"][0]
