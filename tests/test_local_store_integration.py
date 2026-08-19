"""Integration tests proving SQLite store precedence over Alpha Vantage and automatic caching."""
from __future__ import annotations

import tempfile
import gc
from pathlib import Path
from typing import Any
import pytest

from mna_lbo_engine.modules.data_loader import FinancialDataLoader
from mna_lbo_engine.modules.local_financial_store import LocalFinancialStore
from mna_lbo_engine.modules.alpha_vantage_provider import AlphaVantageProvider
from mna_lbo_engine.modules import r_risk_engine


class MockAlphaVantageProvider:
    """Mock provider to verify when Alpha Vantage is called or bypassed."""

    def __init__(self, payloads: dict[str, dict[str, Any]] | None = None) -> None:
        self.payloads = payloads or {}
        self.calls: list[str] = []

    def fetch_company_financials(self, ticker: str) -> dict[str, Any]:
        self.calls.append(ticker)
        if ticker in self.payloads:
            return self.payloads[ticker].copy()
        return {
            "ticker": ticker,
            "company_name": f"{ticker} Live Corp",
            "exchange": "NASDAQ",
            "sector": "Technology",
            "currency": "USD",
            "current_price": 150.0,
            "market_cap": 1500000000.0,
            "shares_outstanding": 10000000.0,
            "revenue": 500000000.0,
            "ebitda": 150000000.0,
            "ebit": 120000000.0,
            "net_income": 90000000.0,
            "total_debt": 50000000.0,
            "cash_and_equivalents": 30000000.0,
            "book_equity": 80000000.0,
            "historical_prices": [
                {"date": "2024-01-01", "close": 140.0, "volume": 100000},
                {"date": "2024-01-02", "close": 145.0, "volume": 110000},
            ],
            "provenance": {"source": "Alpha Vantage", "provenance": "LIVE"},
            "_provenance": "LIVE",
        }


@pytest.fixture
def integration_fixture():
    """Set up an isolated SQLite store and mock provider."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_db = Path(f.name)

    store = LocalFinancialStore(db_path=temp_db)
    mock_provider = MockAlphaVantageProvider()
    loader = FinancialDataLoader(provider=mock_provider, store=store)

    yield loader, store, mock_provider

    del loader
    del store
    gc.collect()
    try:
        temp_db.unlink(missing_ok=True)
        temp_db.with_name(temp_db.name + "-wal").unlink(missing_ok=True)
        temp_db.with_name(temp_db.name + "-shm").unlink(missing_ok=True)
    except OSError:
        pass


def test_1_seeded_company_bypasses_alpha_vantage(integration_fixture):
    """TEST 1: Seed AAPL into SQLite. Request AAPL. Verify Alpha Vantage is NOT called."""
    loader, store, mock_provider = integration_fixture

    seeded_aapl = {
        "ticker": "AAPL",
        "company_name": "Apple Inc. (Local Seed)",
        "exchange": "NASDAQ",
        "sector": "Information Technology",
        "currency": "USD",
        "current_price": 225.0,
        "market_cap": 3400000000000.0,
        "shares_outstanding": 15000000000.0,
        "revenue": 385000000000.0,
        "ebitda": 130000000000.0,
        "ebit": 115000000000.0,
        "net_income": 100000000000.0,
        "total_debt": 105000000000.0,
        "cash_and_equivalents": 60000000000.0,
        "book_equity": 75000000000.0,
        "period": "2024-09-30",
        "provenance": {"source": "Local Store", "provenance": "LIVE"},
    }
    store.save_company(seeded_aapl)

    # Request AAPL
    result = loader.fetch_company_financials("AAPL")

    assert result is not None
    assert result["ticker"] == "AAPL"
    assert result["company_name"] == "Apple Inc. (Local Seed)"
    # CRITICAL: Verify Alpha Vantage was never contacted
    assert len(mock_provider.calls) == 0


def test_2_unseeded_ticker_calls_alpha_vantage(integration_fixture):
    """TEST 2: Request a ticker not in SQLite. Verify Alpha Vantage is called."""
    loader, store, mock_provider = integration_fixture

    assert store.get_company("MSFT") is None

    # Request MSFT
    result = loader.fetch_company_financials("MSFT")

    assert result is not None
    assert result["ticker"] == "MSFT"
    # Verify Alpha Vantage was called exactly once for MSFT
    assert mock_provider.calls == ["MSFT"]


def test_3_successful_alpha_vantage_persists_to_sqlite(integration_fixture):
    """TEST 3: Alpha Vantage returns a company. Verify company is automatically persisted into SQLite."""
    loader, store, mock_provider = integration_fixture

    assert store.get_company("NVDA") is None

    # Fetch from provider
    result = loader.fetch_company_financials("NVDA")
    assert result["ticker"] == "NVDA"
    assert mock_provider.calls == ["NVDA"]

    # Verify automatically persisted into SQLite
    persisted = store.get_company("NVDA")
    assert persisted is not None
    assert persisted["ticker"] == "NVDA"
    assert persisted["company_name"] == "NVDA Live Corp"
    assert persisted["revenue"] == 500000000.0

    # Next fetch must hit SQLite and NOT call provider again
    second_result = loader.fetch_company_financials("NVDA")
    assert second_result["ticker"] == "NVDA"
    assert len(mock_provider.calls) == 1  # Still 1 call, second fetch was local


def test_4_risk_engines_receive_stored_historical_prices(integration_fixture):
    """TEST 4: Company exists locally with historical prices. Verify Risk engines receive stored prices."""
    loader, store, mock_provider = integration_fixture

    # 100 days of historical prices with distinct price movements
    dates_and_prices = [
        {"date": f"2024-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}", "open": 100.0 + (i * 0.5), "high": 102.0 + (i * 0.5), "low": 99.0 + (i * 0.5), "close": 100.0 + (i * 0.5), "volume": 1000000 + i * 100}
        for i in range(100)
    ]

    company_with_prices = {
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "market_cap": 3000000000000.0,
        "total_debt": 100000000000.0,
        "historical_prices": dates_and_prices,
    }
    store.save_company(company_with_prices)

    financials = loader.fetch_company_financials("AAPL")
    assert len(financials["historical_prices"]) == 100

    # Execute VaR / CVaR risk calculation
    var_result = r_risk_engine.run_var_cvar(financials)
    assert var_result["status"] == "VALID"
    assert "historical_var" in var_result
    assert "historical_cvar" in var_result
    assert var_result["observations"] == 99

    # Execute Regime shift risk calculation
    regime_result = r_risk_engine.run_regime(financials)
    assert regime_result["status"] == "VALID"
    assert "current_regime" in regime_result

    # Execute Tail Risk calculation
    tail_result = r_risk_engine.run_tail_risk(financials)
    assert tail_result["status"] == "VALID"
    assert "threshold" in tail_result
    assert tail_result["sample_size"] == 99
