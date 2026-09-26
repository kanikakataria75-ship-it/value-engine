"""HTTP contract tests against a database built from the committed snapshot."""
from __future__ import annotations

import io

import openpyxl
import pytest


def body(response):
    payload = response.json()
    assert set(payload) == {"status", "data", "warnings", "errors", "provenance"}
    return payload


def test_meta_reports_real_counts(api, snapshot_store):
    meta = body(api.get("/api/meta"))["data"]
    assert meta["company_count"] == snapshot_store.get_company_count()
    assert meta["price_rows"] > 100_000
    assert any(fx["pair"] == "USDINR" for fx in meta["fx"])
    assert meta["llm_providers"] == []


def test_local_company_is_labelled_local_with_quality(api):
    payload = body(api.get("/api/company/AAPL"))
    assert payload["status"] == "LOCAL"
    assert payload["provenance"]["source_type"] == "LOCAL"
    data = payload["data"]
    assert data["country"] == "United States" and data["quality"]["fields_total"] == 17
    assert len(data["historical_prices"]) > 200


def test_unknown_ticker_is_404_with_envelope(api):
    response = api.get("/api/company/NOPE999")
    assert response.status_code == 404 and body(response)["status"] == "UNAVAILABLE"


def test_invalid_input_is_422_with_readable_message(api):
    response = api.post("/api/valuation/intrinsic", json={"ticker": "AAPL", "dcf": {"wacc": 3}})
    payload = body(response)
    assert response.status_code == 422 and payload["status"] == "INVALID"
    assert "dcf.wacc" in payload["errors"][0]


def test_search_is_case_insensitive_and_currency_aware(api):
    results = body(api.get("/api/companies/search?q=reliance"))["data"]["results"]
    assert results[0]["ticker"] == "RELIANCE.NSE" and results[0]["currency"] == "INR"


def test_baseline_is_company_specific(api):
    aapl = body(api.get("/api/company/AAPL/baseline"))["data"]
    wmt = body(api.get("/api/company/WMT/baseline"))["data"]
    assert aapl["dcf"]["ebitda_margin"] == pytest.approx(aapl["actuals"]["ebitda_margin"])
    assert wmt["dcf"]["ebitda_margin"] < 0.15 < aapl["dcf"]["ebitda_margin"]
    india = body(api.get("/api/company/RELIANCE.NSE/baseline"))["data"]
    assert india["market"]["currency"] == "INR" and "local market" in india["wacc_build"]["beta_source"]


def test_intrinsic_uses_scenario_overrides(api):
    base = body(api.post("/api/valuation/intrinsic", json={"ticker": "AAPL"}))["data"]
    higher = body(api.post("/api/valuation/intrinsic", json={"ticker": "AAPL", "dcf": {"wacc": base["inputs"]["wacc"] + 0.02}}))["data"]
    assert base["method"] == "dcf" and higher["implied_share_price"] < base["implied_share_price"]


def test_banks_get_the_excess_return_model_and_no_lbo(api):
    assert body(api.post("/api/valuation/intrinsic", json={"ticker": "HDFCBANK.NSE"}))["data"]["method"] == "excess_return"
    assert body(api.post("/api/lbo/run", json={"ticker": "HDFCBANK.NSE"}))["status"] == "INVALID"
    assert body(api.post("/api/risk/monte-carlo", json={"ticker": "JPM"}))["status"] == "UNAVAILABLE"


def test_cross_currency_deal_is_fx_converted(api):
    data = body(api.post("/api/mna/run", json={"ticker": "RELIANCE.NSE", "mna": {"acquirer_ticker": "MSFT"}}))["data"]
    msft = body(api.get("/api/company/MSFT"))["data"]
    assert data["currency"] == "USD" and data["fx"]["from_currency"] == "INR"
    assert data["new_shares_issued"] < 0.2 * msft["shares_outstanding"]


def test_mna_requires_an_acquirer(api):
    assert body(api.post("/api/mna/run", json={"ticker": "AAPL"}))["status"] == "INVALID"


def test_lbo_and_stress(api):
    lbo = body(api.post("/api/lbo/run", json={"ticker": "WMT"}))["data"]
    assert sum(lbo["attribution"].values()) == pytest.approx(lbo["value_creation"], rel=1e-6)
    names = [s["name"] for s in body(api.post("/api/lbo/stress", json={"ticker": "WMT"}))["data"]["scenarios"]]
    assert names[0] == "Base case" and "Combined downside" in names


def test_comps_prefers_same_country_peers(api):
    data = body(api.get("/api/comps/AAPL"))["data"]
    assert data["peer_count"] >= 5
    assert sum(1 for p in data["peers"] if p["country"] == "United States") > data["peer_count"] / 2


def test_monte_carlo_is_reproducible_and_market_based(api):
    request = {"ticker": "WMT", "iterations": 2000, "seed": 7}
    first = body(api.post("/api/risk/monte-carlo", json=request))["data"]
    second = body(api.post("/api/risk/monte-carlo", json=request))["data"]
    assert first["metrics"] == second["metrics"]
    assert 0 <= first["metrics"]["prob_below_market"] <= 1


@pytest.mark.parametrize("path", ["var", "evt", "regime", "factors", "merton"])
def test_risk_endpoints(api, path):
    payload = body(api.get(f"/api/risk/{path}/AAPL"))
    assert payload["status"] in {"VALID", "REVIEW_REQUIRED"}


def test_copula_handles_cross_market_pairs(api):
    data = body(api.get("/api/risk/copula/AAPL/RELIANCE.NSE"))["data"]
    assert data["observations"] > 150 and data["selected_copula"]


def test_confidence_components_are_computed(api):
    data = body(api.post("/api/risk/confidence", json={"ticker": "AAPL"}))["data"]
    assert data["label"] in {"High", "Moderate", "Low"}
    assert {c["key"] for c in data["components"]} == {"data_quality", "dispersion", "agreement", "terminal_reliance", "evidence_depth"}


def test_expectations_and_universe_radar(api, snapshot_store):
    data = body(api.post("/api/expectations", json={"ticker": "AAPL"}))["data"]
    assert data["method"] == "dcf" and data["narrative"]
    radar = body(api.get("/api/expectations/universe"))["data"]
    assert len(radar["rows"]) == snapshot_store.get_company_count()
    assert radar["summary"]["most_optimistic"]


def test_model_health_does_not_call_a_dilutive_deal_invalid(api):
    data = body(api.post("/api/model-health", json={"ticker": "AAPL", "mna": {"acquirer_ticker": "MSFT"}}))["data"]
    dilutive = [f for f in data["flags"] if f["code"] == "DILUTIVE"]
    assert all(f["severity"] == "INFO" for f in dilutive)
    assert data["acquirer_ticker"] == "MSFT" and data["scorecard"]["components"]


def test_excel_export_contains_live_formulas(api):
    response = api.post("/api/reports/excel", json={"ticker": "AAPL", "mna": {"acquirer_ticker": "MSFT"}})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats")
    workbook = openpyxl.load_workbook(io.BytesIO(response.content))
    assert {"Assumptions", "DCF", "Accretion", "LBO", "Checks"} <= set(workbook.sheetnames)
    assert str(workbook["DCF"]["C5"].value).startswith("=")


def test_token_auth_when_configured(api, monkeypatch):
    monkeypatch.setenv("VALUENGINE_API_TOKEN", "s3cret")
    assert api.get("/api/meta").status_code == 401
    assert api.get("/api/meta", headers={"Authorization": "Bearer s3cret"}).status_code == 200
    assert api.get("/api/meta", headers={"X-API-Key": "s3cret"}).status_code == 200
    assert api.get("/api/health").status_code == 200


def test_copilot_rate_limit(api):
    statuses = [api.post("/api/ai/copilot", json={"message": "hi", "ticker": "AAPL"}).status_code for _ in range(21)]
    assert statuses[:20] == [200] * 20 and statuses[20] == 429
