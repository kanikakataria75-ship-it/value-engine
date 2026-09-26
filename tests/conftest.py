"""Shared fixtures.

Unit tests use small synthetic companies with hand-checkable numbers. API tests run against a
temporary database built from the committed snapshot (data/snapshot/), never the developer's
own database, and with every external credential removed.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ["VALUENGINE_WARMUP"] = "0"
for key in ("GEMINI_API_KEY", "GROQ_API_KEY", "ALPHA_VANTAGE_API_KEY", "VALUENGINE_API_TOKEN"):
    os.environ[key] = ""


def make_company(**overrides) -> dict:
    """A simple operating company: revenue 100, EBITDA 20, EBIT 15 (units are arbitrary)."""
    company = {
        "ticker": "TESTCO", "company_name": "Test Company", "sector": "Industrials", "industry": "Machinery",
        "currency": "USD", "exchange": "NYQ", "current_price": 10.0, "shares_outstanding": 10.0, "market_cap": 100.0,
        "revenue": 100.0, "ebitda": 20.0, "ebit": 15.0, "net_income": 10.0, "eps": 1.0, "operating_cash_flow": 18.0,
        "capex": 6.0, "d_and_a": 5.0, "total_debt": 30.0, "cash_and_equivalents": 10.0, "book_equity": 50.0,
        "total_assets": 120.0, "total_liabilities": 70.0, "beta": 1.1, "period": "2025-12-31",
        "retrieved_at": "2026-09-01T00:00:00+00:00", "provenance": {"derived_fields": []}, "historical_prices": [],
    }
    company.update(overrides)
    return company


def make_bank(**overrides) -> dict:
    bank = make_company(
        ticker="BANKCO", company_name="Bank Co", sector="Financial Services", industry="Banks - Regional",
        revenue=50.0, ebitda=None, ebit=20.0, net_income=15.0, book_equity=100.0, total_assets=1000.0,
        total_liabilities=900.0, total_debt=200.0, capex=None, d_and_a=None, market_cap=150.0,
    )
    bank.update(overrides)
    return bank


@pytest.fixture
def company() -> dict:
    return make_company()


@pytest.fixture
def bank() -> dict:
    return make_bank()


@pytest.fixture(scope="session")
def snapshot_store(tmp_path_factory: pytest.TempPathFactory):
    from mna_lbo_engine.modules.local_financial_store import LocalFinancialStore
    from mna_lbo_engine.modules.snapshot import import_snapshot, snapshot_available

    if not snapshot_available():
        pytest.skip("data/snapshot is not available")
    store = LocalFinancialStore(tmp_path_factory.mktemp("db") / "snapshot.db")
    import_snapshot(store)
    return store


@pytest.fixture
def api(snapshot_store):
    """TestClient bound to the snapshot database, with caches and rate limits reset."""
    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.security import limiter
    from backend.services import valuation_service
    from mna_lbo_engine.modules import local_financial_store

    local_financial_store.set_default_store(snapshot_store)
    valuation_service.reset_caches()
    limiter.reset()
    with TestClient(app) as client:
        yield client
    local_financial_store.set_default_store(None)
    valuation_service.reset_caches()


@pytest.fixture
def temp_store(tmp_path: Path):
    from mna_lbo_engine.modules.local_financial_store import LocalFinancialStore

    return LocalFinancialStore(tmp_path / "test.db")
