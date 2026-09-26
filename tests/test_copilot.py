"""Copilot orchestration: provider fallback, streaming protocol and the offline analyst."""
from __future__ import annotations

import json

import pytest

from backend.schemas.models import ChatMessage, CopilotRequest
from backend.services.ai_provider import CopilotOrchestrator, ProviderError
from backend.services.offline_analyst import _money, detect_intent


class FakeProvider:
    def __init__(self, name, answer=None, error=None, chunks=None):
        self.name, self.model = name, f"{name}-model"
        self.answer, self.error, self.chunks = answer, error, chunks
        self.seen = []

    def generate(self, system, messages):
        self.seen.append((system, messages))
        if self.error:
            raise ProviderError(self.error)
        return self.answer

    def stream(self, system, messages):
        if self.error:
            raise ProviderError(self.error)
        yield from self.chunks or []


def orchestrator(monkeypatch, providers):
    orch = CopilotOrchestrator()
    monkeypatch.setattr(orch, "providers", lambda: providers)
    return orch


def events(stream):
    parsed = []
    for block in "".join(stream).strip().split("\n\n"):
        event, data = block.split("\n", 1)
        parsed.append((event.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return parsed


def test_auth_failure_on_primary_falls_back_to_secondary(api, monkeypatch):
    primary = FakeProvider("Gemini", error="Gemini rejected the API key (HTTP 401).")
    secondary = FakeProvider("Groq", answer="From Groq")
    result = orchestrator(monkeypatch, [primary, secondary]).answer(CopilotRequest(message="Explain", ticker="AAPL"))
    assert result["provider"] == "Groq" and result["is_fallback"] is True and result["mode"] == "llm"
    assert "401" in result["errors"][0]


def test_history_and_scenario_context_reach_the_model(api, monkeypatch):
    provider = FakeProvider("Gemini", answer="ok")
    request = CopilotRequest(message="And the LBO?", ticker="AAPL", page="lbo",
                             history=[ChatMessage(role="user", content="Explain the DCF"),
                                      ChatMessage(role="assistant", content="The DCF says...")],
                             scenario={"ticker": "AAPL", "dcf": {"wacc": 0.11}})
    orchestrator(monkeypatch, [provider]).answer(request)
    system, messages = provider.seen[0]
    assert [m.role for m in messages] == ["user", "assistant", "user"]
    assert "[Page: lbo]" in messages[-1].content
    assert '"wacc": 0.11' in system and "VALUENGINE CONTEXT" in system


def test_all_providers_failing_uses_the_offline_analyst(api, monkeypatch):
    failing = FakeProvider("Gemini", error="Gemini temporary provider failure (HTTP 503).")
    result = orchestrator(monkeypatch, [failing]).answer(CopilotRequest(message="What is priced in?", ticker="AAPL"))
    assert result["mode"] == "offline" and result["provider"] == "Offline analyst"
    assert "pricing" in result["answer"] and result["errors"]


def test_stream_protocol_and_fallback_before_first_token(api, monkeypatch):
    broken = FakeProvider("Gemini", error="Gemini rate limit exceeded (HTTP 429).")
    working = FakeProvider("Groq", chunks=["Hello ", "world"])
    parsed = events(orchestrator(monkeypatch, [broken, working]).stream(CopilotRequest(message="hi", ticker="AAPL")))
    assert [e for e, _ in parsed] == ["meta", "delta", "delta", "done"]
    assert parsed[0][1]["provider"] == "Groq" and parsed[0][1]["is_fallback"] is True
    assert "".join(d["text"] for e, d in parsed if e == "delta") == "Hello world"


def test_stream_via_http_without_keys_is_offline(api):
    response = api.post("/api/ai/copilot/stream", json={"message": "Explain the valuation", "ticker": "WMT"})
    assert response.headers["content-type"].startswith("text/event-stream")
    parsed = events([response.text])
    assert parsed[0][0] == "meta" and parsed[0][1]["mode"] == "offline" and parsed[-1][0] == "done"


def test_memo_offline_contains_every_section(api):
    markdown = api.post("/api/ai/memo", json={"ticker": "AAPL"}).json()["data"]["markdown"]
    for heading in ("## 1. Valuation", "## 2. What the market is pricing in", "## 3. Relative value",
                    "## 4. Transaction perspectives", "## 5. Key risks"):
        assert heading in markdown


@pytest.mark.parametrize("message, intent", [
    ("What is the market pricing in?", "expectations"), ("Is this deal accretive?", "mna"),
    ("What IRR does a sponsor get?", "lbo"), ("How do peers compare?", "comps"),
    ("What are the biggest risks?", "risk"), ("Explain this valuation", "valuation"), ("hello", "overview"),
])
def test_offline_intents(message, intent):
    assert detect_intent(message) == intent


def test_offline_money_puts_the_sign_before_the_currency():
    assert _money(-125.7e9, "USD") == "-$125.7B"
    assert _money(-3.4e9, "INR") == "-₹340 Cr"
    assert _money(-12.5, "USD", precise=True) == "-$12.50"
    assert _money(None, "USD") == "n/a"
