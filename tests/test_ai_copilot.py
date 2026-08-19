import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_ai_copilot_no_keys_configured(monkeypatch):
    # Ensure keys are clear
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    
    # Reload orchestrator or just set keys to empty on it
    from backend.services.ai_provider import copilot_orchestrator
    monkeypatch.setattr(copilot_orchestrator, "gemini_key", "")
    monkeypatch.setattr(copilot_orchestrator, "groq_key", "")
    
    payload = {
        "message": "Explain DCF",
        "ticker": "AAPL",
        "context_scope": "current_company",
        "page_context": "dashboard"
    }
    
    response = client.post("/api/ai/copilot", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UNAVAILABLE"
    assert data["data"]["provider"] == "NOT_CONFIGURED"

def test_ai_copilot_context_building(monkeypatch):
    from backend.services.ai_provider import copilot_orchestrator
    
    # Should be able to gather context for a known local ticker
    ctx = copilot_orchestrator.gather_context("MSFT", mode="local")
    
    assert "company" in ctx
    assert ctx["company"]["ticker"] == "MSFT"
    assert "fundamentals" in ctx
    assert "dcf" in ctx
    assert "lbo" in ctx
