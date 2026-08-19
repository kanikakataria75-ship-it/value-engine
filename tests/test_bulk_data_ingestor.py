"""Unit tests for the BulkDataIngestor framework and validation rules."""
from __future__ import annotations

import csv
import gc
from pathlib import Path
import tempfile
import pytest

from mna_lbo_engine.modules.bulk_data_ingestor import BulkDataIngestor, MIN_REQUIRED_PRICE_RECORDS
from mna_lbo_engine.modules.local_financial_store import LocalFinancialStore
from mna_lbo_engine.modules.market_data_provider import MockMarketDataProvider


@pytest.fixture
def ingestor_env():
    """Create isolated temporary environment for bulk ingestion tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        dir_path = Path(temp_dir)
        db_path = dir_path / "test_ingest.db"
        universe_path = dir_path / "universe.csv"
        success_path = dir_path / "success.csv"
        failures_path = dir_path / "failures.csv"

        # Create sample universe CSV
        with open(universe_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ticker", "company_name", "exchange", "country", "currency", "sector", "industry", "priority"])
            writer.writerow(["AAPL", "Apple Inc.", "NASDAQ", "USA", "USD", "Information Technology", "Consumer Electronics", "Tier 1"])
            writer.writerow(["MSFT", "Microsoft Corp", "NASDAQ", "USA", "USD", "Information Technology", "Systems Software", "Tier 1"])
            writer.writerow(["RELIANCE.NSE", "Reliance Industries", "NSE", "India", "INR", "Energy", "Oil & Gas", "Tier 1"])

        store = LocalFinancialStore(db_path=db_path)
        provider = MockMarketDataProvider()
        ingestor = BulkDataIngestor(
            provider=provider,
            store=store,
            universe_csv=universe_path,
            success_csv=success_path,
            failures_csv=failures_path,
        )

        yield ingestor, provider, store, dir_path

        del ingestor
        del store
        gc.collect()


def test_1_mock_provider_successful_ingestion(ingestor_env):
    """TEST 1: Mock provider -> successful company -> SQLite."""
    ingestor, provider, store, _ = ingestor_env

    row = {
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "exchange": "NASDAQ",
        "country": "USA",
        "currency": "USD",
        "sector": "Information Technology",
        "industry": "Consumer Electronics",
        "priority": "Tier 1",
    }

    success, status = ingestor.ingest_company(row)
    assert success is True
    assert status == "SUCCESS"

    # Verify company exists in SQLite store
    stored = store.get_company("AAPL")
    assert stored is not None
    assert stored["ticker"] == "AAPL"
    assert stored["revenue"] == 500000000.0
    assert stored["current_price"] == 150.0
    assert len(stored["historical_prices"]) == 250
    assert stored["_provenance"] == "LIVE"


def test_2_missing_required_field_rejected(ingestor_env):
    """TEST 2: Missing required field (e.g. revenue, ebit, shares) -> rejected."""
    ingestor, provider, store, _ = ingestor_env

    # Configure mock provider with invalid revenue
    provider.responses["BAD_REV"] = {
        "income_statement": {"period": "2024-12-31", "revenue": -100.0, "ebit": 50.0, "net_income": 30.0}
    }

    row = {"ticker": "BAD_REV", "company_name": "Bad Rev Corp", "country": "USA", "currency": "USD"}
    success, reason = ingestor.ingest_company(row)
    assert success is False
    assert "revenue must be strictly positive" in reason
    assert store.get_company("BAD_REV") is None


def test_3_under_200_prices_rejected(ingestor_env):
    """TEST 3: <200 prices -> rejected."""
    ingestor, provider, store, _ = ingestor_env

    # Configure only 50 prices
    short_prices = [{"date": f"2024-01-{i:02d}", "close": 100.0, "volume": 1000} for i in range(1, 51)]
    provider.responses["FEW_PRICES"] = {"historical_prices": short_prices}

    row = {"ticker": "FEW_PRICES", "company_name": "Few Prices Inc.", "country": "USA", "currency": "USD"}
    success, reason = ingestor.ingest_company(row)
    assert success is False
    assert f"at least {MIN_REQUIRED_PRICE_RECORDS} daily records" in reason
    assert store.get_company("FEW_PRICES") is None


def test_4_200_plus_prices_accepted(ingestor_env):
    """TEST 4: 200+ prices -> accepted."""
    ingestor, provider, store, _ = ingestor_env

    # 220 prices
    valid_prices = [
        {"date": f"2024-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}", "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 10000}
        for i in range(220)
    ]
    provider.responses["GOOD_PRICES"] = {"historical_prices": valid_prices}

    row = {"ticker": "GOOD_PRICES", "company_name": "Good Prices Inc.", "country": "USA", "currency": "USD"}
    success, status = ingestor.ingest_company(row)
    assert success is True
    assert status == "SUCCESS"

    stored = store.get_company("GOOD_PRICES")
    assert stored is not None
    assert len(stored["historical_prices"]) == 220


def test_5_failed_company_logged_in_failures_csv(ingestor_env):
    """TEST 5: Failed company -> logged in ingestion_failures.csv."""
    ingestor, provider, store, _ = ingestor_env

    provider.responses["FAIL_CO"] = {
        "profile": {"shares_outstanding": 0.0}  # Invalid shares
    }

    row = {"ticker": "FAIL_CO", "company_name": "Fail Co", "country": "USA", "currency": "USD"}
    success, reason = ingestor.ingest_company(row)
    assert success is False

    # Check failures.csv
    assert ingestor.failures_csv.exists()
    with open(ingestor.failures_csv, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 1
        assert reader[0]["ticker"] == "FAIL_CO"
        assert reader[0]["error_type"] == "VALIDATION_ERROR"
        assert "shares_outstanding must be strictly positive" in reader[0]["reason"]


def test_6_resume_logic_skips_successful_ticker(ingestor_env):
    """TEST 6: Resume logic skips already successful ticker without re-querying provider."""
    ingestor, provider, store, _ = ingestor_env

    row = {"ticker": "AAPL", "company_name": "Apple Inc.", "country": "USA", "currency": "USD"}

    # First ingestion
    success1, status1 = ingestor.ingest_company(row, overwrite=False)
    assert success1 is True
    assert status1 == "SUCCESS"
    initial_calls = len(provider.calls)

    # Second ingestion with overwrite=False
    success2, status2 = ingestor.ingest_company(row, overwrite=False)
    assert success2 is True
    assert status2 == "SKIPPED_ALREADY_EXISTS"
    # No new provider calls made
    assert len(provider.calls) == initial_calls


def test_7_overwrite_flag_updates_existing_company(ingestor_env):
    """TEST 7: Existing DB company is updated when overwrite=True."""
    ingestor, provider, store, _ = ingestor_env

    row = {"ticker": "MSFT", "company_name": "Microsoft Corp", "country": "USA", "currency": "USD"}

    # First ingestion
    ingestor.ingest_company(row, overwrite=False)
    initial_stored = store.get_company("MSFT")
    assert initial_stored["revenue"] == 500000000.0

    # Modify provider response for MSFT
    provider.responses["MSFT"] = {
        "income_statement": {"period": "2024-12-31", "revenue": 600000000.0, "ebit": 150000000.0, "net_income": 120000000.0, "eps": 12.0}
    }

    # Re-run with overwrite=True
    success, status = ingestor.ingest_company(row, overwrite=True)
    assert success is True
    assert status == "SUCCESS"

    updated_stored = store.get_company("MSFT")
    assert updated_stored["revenue"] == 600000000.0
    assert store.get_company_count() == 1
