from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_company_returns_valid_provenance():
    response = client.get("/api/company/AAPL")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"LIVE", "CACHED", "RATE_LIMITED", "DEMO"}
    assert payload["provenance"]["source"] in {
        "Alpha Vantage",
        "Alpha Vantage (Cached)",
        "YahooFinance",
        "LOCAL_DB",
        "LocalFinancialStore",
        "RATE_LIMITED",
        "DEMO",
    }


def test_dcf_api_uses_engine_and_serializes_projections():
    response = client.post("/api/dcf/run", json={"ticker": "AAPL"})
    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "VALID"
    assert len(payload["data"]["projections_df"]) == 5


def test_dcf_invalid_is_explicit_not_fabricated():
    response = client.post("/api/dcf/run", json={"ticker": "AAPL", "wacc": 0.02, "terminal_growth_rate": 0.03})
    payload = response.json()
    assert payload["status"] == "INVALID"
    assert payload["data"] == {}
    assert payload["errors"]


def test_mna_lbo_and_comps_endpoints():
    assert client.post("/api/mna/run", json={"target_ticker": "AAPL", "acquirer_ticker": "MSFT"}).json()["status"] == "VALID"
    assert client.post("/api/lbo/run", json={"ticker": "AAPL"}).json()["status"] == "VALID"
    assert client.get("/api/comps/trading/AAPL").json()["status"] == "VALID"
    assert client.get("/api/comps/transactions/AAPL").json()["status"] == "UNAVAILABLE"


def test_model_health_data_quality_and_excel_export():
    assert client.get("/api/model-health/AAPL").json()["status"] in {"VALID", "REVIEW_REQUIRED", "INVALID"}
    assert client.get("/api/data-quality/AAPL").json()["status"] == "VALID"
    export = client.post("/api/reports/excel", json={"target_ticker": "AAPL", "acquirer_ticker": "MSFT"})
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument")


def test_search_companies_endpoint():
    response = client.get("/api/companies/search?q=reliance&mode=local")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "VALID"
    results = payload["data"]["results"]
    assert len(results) > 0
    assert any("RELIANCE" in r["ticker"] for r in results)

    response_aapl = client.get("/api/companies/search?q=Apple&mode=local")
    assert response_aapl.status_code == 200
    payload_aapl = response_aapl.json()
    assert any(r["ticker"] == "AAPL" for r in payload_aapl["data"]["results"])


def test_local_mode_unavailable_for_nonexistent_ticker():
    response = client.get("/api/company/NONEXISTENT_TICKER_999?mode=local")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "UNAVAILABLE"
    assert "not available in Local Dataset" in payload["errors"][0]


def test_trading_comps_local_mode_with_sector_peers():
    response = client.get("/api/comps/trading/RELIANCE.NSE?mode=local")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "VALID"
    assert payload["data"]["implied_share_price_median"] > 0
    assert len(payload["data"]["peer_multiples_df"]) >= 2
