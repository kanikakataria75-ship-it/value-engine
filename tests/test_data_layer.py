"""Local store, snapshot, ingestion and data-loader behaviour (no network)."""
from __future__ import annotations

from pathlib import Path

import pytest

from conftest import make_company
from mna_lbo_engine.modules.alpha_vantage_provider import AlphaVantageRateLimited, AlphaVantageUnavailable
from mna_lbo_engine.modules.bulk_data_ingestor import BulkDataIngestor
from mna_lbo_engine.modules.data_loader import FinancialDataLoader
from mna_lbo_engine.modules.fx import FxConverter
from mna_lbo_engine.modules.local_financial_store import LocalFinancialStore, normalize_sector
from mna_lbo_engine.modules.market_data_provider import MockMarketDataProvider
from mna_lbo_engine.modules.snapshot import export_snapshot, import_snapshot

PRICES = [{"date": f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", "close": 100.0 + i, "open": 99.0, "high": 101.0,
           "low": 98.0, "volume": 1000.0} for i in range(220)]


def test_local_data_is_labelled_local_never_live(temp_store):
    temp_store.save_company({**make_company(ticker="AAA"), "provenance": {"provider": "YahooFinance", "source_type": "LIVE"}})
    company = temp_store.get_company("aaa")
    assert company["provenance"]["source_type"] == "LOCAL"
    assert company["provenance"]["origin"] == "YahooFinance"
    assert company["period"] == "2025-12-31"


def test_sector_names_are_normalised(temp_store):
    assert normalize_sector("TECHNOLOGY") == "Technology"
    assert normalize_sector("LIFE SCIENCES") == "Healthcare"
    temp_store.save_company(make_company(ticker="BBB", sector="FINANCIAL SERVICES"))
    assert temp_store.get_company("BBB")["sector"] == "Financial Services"


def test_preserve_classification_keeps_local_taxonomy(temp_store):
    temp_store.save_company(make_company(ticker="CCC", sector="Technology", industry="Software - Infrastructure"))
    temp_store.save_company(make_company(ticker="CCC", sector="MANUFACTURING", industry="SERVICES-PREPACKAGED SOFTWARE"),
                            preserve_classification=True)
    company = temp_store.get_company("CCC")
    assert (company["sector"], company["industry"]) == ("Technology", "Software - Infrastructure")


def test_prices_history_and_fx(temp_store):
    temp_store.save_company({**make_company(ticker="DDD"), "historical_prices": PRICES,
                             "fundamentals_history": [{"period_end": "2024-12-31", "revenue": 90.0},
                                                      {"period_end": "2025-12-31", "revenue": 100.0}]})
    assert len(temp_store.get_daily_prices("DDD")) == 220
    assert [p["close"] for p in temp_store.get_daily_prices("DDD", limit=3)] == [317.0, 318.0, 319.0]
    assert [r["period_end"] for r in temp_store.get_history("DDD")] == ["2024-12-31", "2025-12-31"]
    temp_store.save_fx_rates("USDINR", [("2026-09-01", 90.0), ("2026-09-02", 91.0)], "test")
    assert temp_store.get_fx_rate("USDINR")["rate"] == 91.0
    assert temp_store.get_fx_rate("USDINR", on_or_before="2026-09-01")["rate"] == 90.0
    assert FxConverter(temp_store).convert(910.0, "INR", "USD") == pytest.approx(10.0)
    assert temp_store.to_usd(182.0, "INR") == pytest.approx(2.0)


def test_search_ranks_by_usd_market_cap(temp_store):
    temp_store.save_fx_rates("USDINR", [("2026-09-01", 100.0)], "test")
    temp_store.save_company(make_company(ticker="BIGUS", company_name="Big US", market_cap=1_000.0))
    temp_store.save_company(make_company(ticker="IN.NSE", company_name="India Co", currency="INR", market_cap=50_000.0))
    order = [r["ticker"] for r in temp_store.search_companies("", limit=5)]
    assert order == ["BIGUS", "IN.NSE"]          # 50,000 INR = 500 USD < 1,000 USD
    assert temp_store.search_companies("in.nse")[0]["country"] == "India"


def test_snapshot_round_trip(temp_store, tmp_path: Path):
    temp_store.save_company({**make_company(ticker="EEE"), "historical_prices": PRICES[:5],
                             "fundamentals_history": [{"period_end": "2025-12-31", "revenue": 100.0}]})
    temp_store.save_fx_rates("USDINR", [("2026-09-01", 90.0)], "test")
    counts = export_snapshot(temp_store, tmp_path / "snap")
    rebuilt = LocalFinancialStore(tmp_path / "rebuilt.db")
    assert import_snapshot(rebuilt, tmp_path / "snap") == counts
    original, copy = temp_store.get_company("EEE"), rebuilt.get_company("EEE")
    for field in ("revenue", "ebitda", "total_debt", "market_cap", "period"):
        assert copy[field] == original[field]
    assert [p["close"] for p in copy["historical_prices"]] == [p["close"] for p in original["historical_prices"]]


def ingestor(store: LocalFinancialStore, tmp_path: Path, responses: dict) -> BulkDataIngestor:
    return BulkDataIngestor(MockMarketDataProvider(responses=responses), store,
                            universe_csv=tmp_path / "universe.csv", success_csv=tmp_path / "ok.csv",
                            failures_csv=tmp_path / "fail.csv")


def test_ingestion_success_and_ebitda_reconciliation(temp_store, tmp_path):
    responses = {"XYZ": {"income_statement": {"period": "2025-12-31", "revenue": 500.0, "ebitda": 90.0, "ebit": 120.0,
                                              "net_income": 80.0, "eps": 8.0, "depreciation": 30.0},
                         "cash_flow": {"period": "2025-12-31", "operating_cash_flow": 110.0, "capex": 25.0,
                                       "depreciation_amortization": 30.0}}}
    ok, status = ingestor(temp_store, tmp_path, responses).ingest_company({"ticker": "XYZ", "company_name": "XYZ"})
    assert (ok, status) == (True, "SUCCESS")
    company = temp_store.get_company("XYZ")
    assert company["ebitda"] == pytest.approx(150.0)             # EBIT 120 + D&A 30, not the inconsistent 90
    assert "ebitda (EBIT + D&A)" in company["provenance"]["derived_fields"]


def test_ingestion_rejects_negative_cash_and_logs_failure(temp_store, tmp_path):
    responses = {"BAD": {"balance_sheet": {"period": "2025-12-31", "total_debt": 10.0, "cash_and_equivalents": -5.0,
                                           "book_equity": 100.0, "total_assets": 200.0, "total_liabilities": 100.0}}}
    run = ingestor(temp_store, tmp_path, responses)
    ok, reason = run.ingest_company({"ticker": "BAD", "company_name": "Bad"})
    assert not ok and temp_store.get_company("BAD") is None
    assert "BAD" in (tmp_path / "fail.csv").read_text(encoding="utf-8")


def test_ingestion_requires_price_history(temp_store, tmp_path):
    responses = {"SHORT": {"historical_prices": PRICES[:20]}}
    ok, reason = ingestor(temp_store, tmp_path, responses).ingest_company({"ticker": "SHORT", "company_name": "Short"})
    assert not ok and "200" in reason


class FailingProvider:
    api_key = "x"

    def __init__(self, error):
        self.error = error

    def fetch_company_financials(self, ticker):
        raise self.error


class LiveProvider:
    api_key = "x"

    def fetch_company_financials(self, ticker):
        return {**make_company(ticker=ticker, revenue=999.0, ebitda=10.0, ebit=50.0, d_and_a=5.0, sector="TECHNOLOGY"),
                "historical_prices": [{"date": "2026-09-01", "close": 1.0}],
                "provenance": {"source_type": "LIVE", "provider": "Alpha Vantage", "derived_fields": []}}


def test_live_mode_falls_back_to_the_local_snapshot(temp_store):
    temp_store.save_company({**make_company(ticker="LLL"), "historical_prices": PRICES})
    loader = FinancialDataLoader(provider=FailingProvider(AlphaVantageUnavailable("no key")), store=temp_store)
    company, status, notice = loader.fetch_company("LLL", "live")
    assert status == "LOCAL_FALLBACK" and company["revenue"] == 100.0 and "no key" in notice
    loader = FinancialDataLoader(provider=FailingProvider(AlphaVantageRateLimited("slow down")), store=temp_store)
    assert loader.fetch_company("LLL", "live")[1] == "RATE_LIMITED"
    assert loader.fetch_company("NOPE", "live")[1] == "UNAVAILABLE"


def test_live_refresh_keeps_adjusted_prices_and_taxonomy(temp_store):
    temp_store.save_company({**make_company(ticker="LIV", sector="Technology"), "historical_prices": PRICES})
    company, status, _ = FinancialDataLoader(provider=LiveProvider(), store=temp_store).fetch_company("LIV", "live")
    assert status == "LIVE" and company["revenue"] == 999.0
    assert company["ebitda"] == pytest.approx(55.0)              # reconciled to EBIT + D&A
    assert company["sector"] == "Technology"
    assert len(temp_store.get_daily_prices("LIV")) == len(PRICES)  # unadjusted live closes were not merged in


def test_local_mode_never_calls_the_provider(temp_store):
    temp_store.save_company(make_company(ticker="LOC"))
    loader = FinancialDataLoader(provider=FailingProvider(AssertionError("network!")), store=temp_store)
    assert loader.fetch_company("LOC", "local")[1] == "LOCAL"
