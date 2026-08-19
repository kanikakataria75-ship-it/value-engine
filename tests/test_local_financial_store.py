"""Unit tests for the LocalFinancialStore SQLite repository layer."""
from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from mna_lbo_engine.modules.local_financial_store import (
    LocalFinancialStore,
    save_company,
    get_company,
    save_daily_prices,
    get_daily_prices,
)


@pytest.fixture
def temp_store():
    """Create an isolated temporary SQLite database for testing."""
    import gc
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = Path(f.name)
    
    store = LocalFinancialStore(db_path=temp_path)
    yield store
    
    del store
    gc.collect()
    try:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        wal_path = temp_path.with_name(temp_path.name + "-wal")
        if wal_path.exists():
            wal_path.unlink(missing_ok=True)
        shm_path = temp_path.with_name(temp_path.name + "-shm")
        if shm_path.exists():
            shm_path.unlink(missing_ok=True)
    except OSError:
        pass


def test_db_initialization(temp_store: LocalFinancialStore):
    """Verify that tables and indexes are created properly."""
    assert temp_store.get_company_count() == 0
    with temp_store._get_connection() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        assert "company_fundamentals" in tables
        assert "daily_prices" in tables

        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}
        assert "idx_fundamentals_sector" in indexes
        assert "idx_daily_prices_ticker_date" in indexes
        assert "idx_daily_prices_date" in indexes


def test_insert_and_get_company(temp_store: LocalFinancialStore):
    """Verify storing and reading a normalized company fundamentals record."""
    sample_aapl = {
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "exchange": "NASDAQ",
        "sector": "Information Technology",
        "industry": "Consumer Electronics",
        "currency": "USD",
        "current_price": 225.50,
        "market_cap": 3450000000000.0,
        "shares_outstanding": 15300000000.0,
        "revenue": 391000000000.0,
        "ebitda": 133000000000.0,
        "ebit": 123000000000.0,
        "net_income": 101000000000.0,
        "eps": 6.60,
        "operating_cash_flow": 118000000000.0,
        "capex": 11000000000.0,
        "d_and_a": 10000000000.0,
        "total_debt": 106000000000.0,
        "cash_and_equivalents": 65000000000.0,
        "book_equity": 74000000000.0,
        "total_assets": 352000000000.0,
        "total_liabilities": 278000000000.0,
        "beta": 1.08,
        "period": "2024-09-28",
        "retrieved_at": "2026-08-18T10:00:00Z",
        "provenance": {
            "source": "Local Store",
            "provenance": "LIVE",
            "period": "2024-09-28",
            "currency": "USD",
        },
    }

    temp_store.save_company(sample_aapl)
    assert temp_store.get_company_count() == 1

    retrieved = temp_store.get_company("AAPL")
    assert retrieved is not None
    assert retrieved["ticker"] == "AAPL"
    assert retrieved["company_name"] == "Apple Inc."
    assert retrieved["currency"] == "USD"
    assert retrieved["current_price"] == 225.50
    assert retrieved["revenue"] == 391000000000.0
    assert retrieved["ebitda"] == 133000000000.0
    assert retrieved["total_debt"] == 106000000000.0
    assert retrieved["cash_and_equivalents"] == 65000000000.0
    assert retrieved["shares_outstanding"] == 15300000000.0
    assert retrieved["provenance"]["period"] == "2024-09-28"
    assert retrieved["_provenance"] == "LIVE"


def test_indian_company_preserves_currency_and_period(temp_store: LocalFinancialStore):
    """Verify Indian ticker with INR currency and length > 12 is stored accurately."""
    sample_reliance = {
        "ticker": "RELIANCE.NSE",
        "company_name": "Reliance Industries Limited",
        "exchange": "NSE",
        "sector": "Energy",
        "industry": "Oil Refining, Petrochemicals & Telecom",
        "currency": "INR",
        "current_price": 2980.0,
        "market_cap": 20150000000000.0,
        "shares_outstanding": 6760000000.0,
        "revenue": 9000000000000.0,
        "ebitda": 1780000000000.0,
        "ebit": 1250000000000.0,
        "net_income": 790000000000.0,
        "eps": 116.8,
        "operating_cash_flow": 1500000000000.0,
        "capex": 1300000000000.0,
        "d_and_a": 530000000000.0,
        "total_debt": 3200000000000.0,
        "cash_and_equivalents": 1900000000000.0,
        "book_equity": 7900000000000.0,
        "total_assets": 17000000000000.0,
        "total_liabilities": 9100000000000.0,
        "beta": 1.15,
        "period": "2024-03-31",
        "retrieved_at": "2026-08-18T10:00:00Z",
    }

    temp_store.save_company(sample_reliance)
    retrieved = temp_store.get_company("RELIANCE.NSE")
    assert retrieved is not None
    assert retrieved["ticker"] == "RELIANCE.NSE"
    assert retrieved["currency"] == "INR"
    assert retrieved["provenance"]["currency"] == "INR"
    assert retrieved["provenance"]["period"] == "2024-03-31"


def test_update_existing_company(temp_store: LocalFinancialStore):
    """Verify updating company fundamentals does not create duplicates."""
    initial = {
        "ticker": "MSFT",
        "company_name": "Microsoft Corp",
        "revenue": 240000000000.0,
        "current_price": 400.0,
    }
    temp_store.save_company(initial)
    assert temp_store.get_company_count() == 1

    updated = {
        "ticker": "MSFT",
        "company_name": "Microsoft Corporation",
        "revenue": 245000000000.0,
        "current_price": 420.0,
    }
    temp_store.save_company(updated)
    assert temp_store.get_company_count() == 1

    retrieved = temp_store.get_company("MSFT")
    assert retrieved is not None
    assert retrieved["company_name"] == "Microsoft Corporation"
    assert retrieved["revenue"] == 245000000000.0
    assert retrieved["current_price"] == 420.0


def test_missing_company_behavior(temp_store: LocalFinancialStore):
    """Verify missing company returns None cleanly."""
    assert temp_store.get_company("UNKNOWN_TICKER") is None
    assert temp_store.get_company("") is None


def test_daily_prices_200_plus_records(temp_store: LocalFinancialStore):
    """Verify saving and retrieving 250 daily historical price records."""
    # First save company
    temp_store.save_company({"ticker": "NVDA", "company_name": "NVIDIA Corp"})

    # Generate 250 daily prices
    prices = [
        {
            "date": f"2024-01-{(i % 28) + 1:02d}",
            "open": 100.0 + i,
            "high": 105.0 + i,
            "low": 99.0 + i,
            "close": 102.5 + i,
            "volume": 50000000.0 + i * 1000,
        }
        for i in range(250)
    ]
    # Unique dates
    import datetime
    base_date = datetime.date(2024, 1, 1)
    for i, p in enumerate(prices):
        d = base_date + datetime.timedelta(days=i)
        p["date"] = str(d)

    saved_count = temp_store.save_daily_prices("NVDA", prices)
    assert saved_count == 250

    # Retrieve all prices
    retrieved_prices = temp_store.get_daily_prices("NVDA")
    assert len(retrieved_prices) == 250
    # Chronological ordering check
    assert retrieved_prices[0]["date"] == "2024-01-01"
    assert retrieved_prices[-1]["date"] == str(base_date + datetime.timedelta(days=249))

    # Retrieve with limit
    latest_50 = temp_store.get_daily_prices("NVDA", limit=50)
    assert len(latest_50) == 50
    assert latest_50[-1]["date"] == retrieved_prices[-1]["date"]


def test_cascade_delete(temp_store: LocalFinancialStore):
    """Verify deleting a company removes its fundamentals and daily prices."""
    temp_store.save_company({
        "ticker": "TSLA",
        "company_name": "Tesla Inc.",
        "historical_prices": [
            {"date": "2024-01-01", "close": 200.0, "volume": 1000000},
            {"date": "2024-01-02", "close": 205.0, "volume": 1200000},
        ]
    })
    assert temp_store.get_company_count() == 1
    assert len(temp_store.get_daily_prices("TSLA")) == 2

    assert temp_store.delete_company("TSLA") is True
    assert temp_store.get_company_count() == 0
    assert len(temp_store.get_daily_prices("TSLA")) == 0


def test_convenience_functions(temp_store: LocalFinancialStore):
    """Verify module-level save_company, get_company, save_daily_prices, get_daily_prices."""
    save_company({"ticker": "GOOGL", "company_name": "Alphabet Inc."}, store=temp_store)
    comp = get_company("GOOGL", store=temp_store)
    assert comp is not None
    assert comp["ticker"] == "GOOGL"

    save_daily_prices("GOOGL", [{"date": "2024-01-01", "close": 140.0}], store=temp_store)
    prices = get_daily_prices("GOOGL", store=temp_store)
    assert len(prices) == 1
    assert prices[0]["close"] == 140.0
