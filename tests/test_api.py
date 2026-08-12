from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_company_returns_valid_provenance():
    response = client.get("/api/company/AAPL")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"LIVE", "CACHED", "RATE_LIMITED", "DEMO"}
    assert payload["provenance"]["source"] in {"Alpha Vantage", "Alpha Vantage (Cached)", "RATE_LIMITED", "DEMO"}


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
