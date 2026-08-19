import pytest
from fastapi.testclient import TestClient

from backend.main import app
from mna_lbo_engine.modules.r_integration import is_r_available

client = TestClient(app)

def test_monte_carlo_endpoint():
    response = client.get("/api/risk/monte-carlo/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    # Should either be VALID or UNAVAILABLE
    assert data["status"] in ["VALID", "UNAVAILABLE", "RATE_LIMITED", "DEMO"]

def test_sensitivity_endpoint():
    response = client.get("/api/risk/sensitivity/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data

def test_var_endpoint():
    response = client.get("/api/risk/var/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["VALID", "UNAVAILABLE", "RATE_LIMITED", "DEMO"]

def test_merton_endpoint():
    response = client.get("/api/risk/merton/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["VALID", "UNAVAILABLE", "RATE_LIMITED", "DEMO"]

def test_regime_endpoint():
    response = client.get("/api/risk/regime/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["VALID", "UNAVAILABLE", "RATE_LIMITED", "DEMO"]

def test_fama_french_endpoint():
    response = client.get("/api/risk/fama-french/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["VALID", "UNAVAILABLE", "RATE_LIMITED", "DEMO"]

def test_evt_endpoint():
    response = client.get("/api/risk/evt/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["VALID", "UNAVAILABLE", "RATE_LIMITED", "DEMO"]

def test_copula_endpoint():
    response = client.get("/api/risk/copula/MSFT/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["VALID", "UNAVAILABLE", "RATE_LIMITED", "DEMO"]

def test_valuation_confidence_endpoint():
    response = client.get("/api/risk/valuation-confidence/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["VALID", "UNAVAILABLE", "RATE_LIMITED", "DEMO"]
