"""ValuAI copilot: grounded LLM answers with streaming, provider fallback and an offline analyst.

The copilot receives the analyst's current scenario (not hard-coded defaults), the conversation
history and a context block computed by the engines. Providers are tried in order (Gemini, Groq by
default); any provider failure falls through to the next, and if none is available the rule-based
offline analyst answers from the same context. API keys are sent in headers, never in URLs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Iterator

import requests

from backend.schemas.models import ChatMessage, CopilotRequest, ScenarioRequest
from backend.services import valuation_service as service
from backend.services.offline_analyst import offline_answer, offline_memo

logger = logging.getLogger(__name__)
TIMEOUT = (10, 60)


class ProviderError(RuntimeError):
    pass


def _raise_for_status(name: str, response: requests.Response) -> None:
    if response.status_code == 200:
        return
    reasons = {400: "rejected the request", 401: "rejected the API key", 403: "denied access",
               404: "does not recognise the configured model", 429: "rate limit exceeded"}
    reason = reasons.get(response.status_code, "temporary provider failure" if response.status_code >= 500 else "request failed")
    raise ProviderError(f"{name} {reason} (HTTP {response.status_code}).")


class LLMProvider(ABC):
    name: str

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    @abstractmethod
    def generate(self, system: str, messages: list[ChatMessage]) -> str: ...

    @abstractmethod
    def stream(self, system: str, messages: list[ChatMessage]) -> Iterator[str]: ...


class GeminiProvider(LLMProvider):
    name = "Gemini"
    base = "https://generativelanguage.googleapis.com/v1beta/models"

    def _body(self, system: str, messages: list[ChatMessage]) -> dict[str, Any]:
        return {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user" if m.role == "user" else "model", "parts": [{"text": m.content}]} for m in messages],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
        }

    def _headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

    @staticmethod
    def _text(payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates") or []
        if not candidates:
            return ""
        return "".join(part.get("text", "") for part in (candidates[0].get("content") or {}).get("parts", []))

    def generate(self, system: str, messages: list[ChatMessage]) -> str:
        try:
            response = requests.post(f"{self.base}/{self.model}:generateContent", headers=self._headers(),
                                     json=self._body(system, messages), timeout=TIMEOUT)
        except requests.RequestException as exc:
            raise ProviderError(f"Gemini network error ({type(exc).__name__}).") from exc
        _raise_for_status(self.name, response)
        text = self._text(response.json())
        if not text:
            raise ProviderError("Gemini returned an empty answer.")
        return text

    def stream(self, system: str, messages: list[ChatMessage]) -> Iterator[str]:
        try:
            response = requests.post(f"{self.base}/{self.model}:streamGenerateContent?alt=sse", headers=self._headers(),
                                     json=self._body(system, messages), timeout=TIMEOUT, stream=True)
        except requests.RequestException as exc:
            raise ProviderError(f"Gemini network error ({type(exc).__name__}).") from exc
        _raise_for_status(self.name, response)
        with response:
            for line in response.iter_lines(decode_unicode=True):
                if line and line.startswith("data:"):
                    text = self._text(json.loads(line[5:].strip()))
                    if text:
                        yield text


class GroqProvider(LLMProvider):
    name = "Groq"
    url = "https://api.groq.com/openai/v1/chat/completions"

    def _body(self, system: str, messages: list[ChatMessage], stream: bool) -> dict[str, Any]:
        return {"model": self.model, "temperature": 0.2, "max_tokens": 2048, "stream": stream,
                "messages": [{"role": "system", "content": system}] + [{"role": m.role, "content": m.content} for m in messages]}

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def generate(self, system: str, messages: list[ChatMessage]) -> str:
        try:
            response = requests.post(self.url, headers=self._headers(), json=self._body(system, messages, False), timeout=TIMEOUT)
        except requests.RequestException as exc:
            raise ProviderError(f"Groq network error ({type(exc).__name__}).") from exc
        _raise_for_status(self.name, response)
        try:
            return response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise ProviderError("Groq returned an unexpected payload.") from exc

    def stream(self, system: str, messages: list[ChatMessage]) -> Iterator[str]:
        try:
            response = requests.post(self.url, headers=self._headers(), json=self._body(system, messages, True),
                                     timeout=TIMEOUT, stream=True)
        except requests.RequestException as exc:
            raise ProviderError(f"Groq network error ({type(exc).__name__}).") from exc
        _raise_for_status(self.name, response)
        with response:
            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                delta = (json.loads(data).get("choices") or [{}])[0].get("delta", {}).get("content")
                if delta:
                    yield delta


SYSTEM_RULES = """You are ValuAI, the analyst copilot inside ValuEngine, a corporate-finance workstation.

Rules:
- Use only the numbers in the VALUENGINE CONTEXT below. Never invent financial data, transactions, prices or sources.
- If something is not in the context, say it is unavailable.
- Distinguish observed data (fundamentals, prices), model outputs (DCF, comps, LBO, M&A, risk), the analyst's
  assumptions (the scenario) and your interpretation.
- Explain drivers, not just outputs. Name the assumption a conclusion depends on.
- Quote amounts in the company's currency (INR amounts in crore where natural).
- Never present an investment recommendation as certain; this is analysis, not advice.
- Be concise and use markdown (short headings, bullets, bold for key numbers).
"""


def _safe(fn: Any) -> Any:
    try:
        return fn()
    except Exception as exc:  # one failing model must not break the copilot
        logger.info("Copilot context component unavailable: %s", exc)
        return None


def _data(envelope: dict[str, Any] | None) -> dict[str, Any] | None:
    if not envelope or envelope.get("status") in {"INVALID", "UNAVAILABLE", "ERROR"}:
        return None
    return envelope.get("data")


def build_context(req: CopilotRequest) -> dict[str, Any]:
    scenario = req.scenario or ScenarioRequest(ticker=req.ticker, mode=req.mode)
    if scenario.ticker != req.ticker.upper():
        scenario = ScenarioRequest(ticker=req.ticker, mode=req.mode)
    company, status = service.load(req.ticker, req.mode)
    baseline = service.baseline_for(company)
    actuals = baseline["actuals"]
    currency = (company.get("currency") or "USD").upper()
    intrinsic = _data(_safe(lambda: service.intrinsic(scenario))) or {}
    comps = _data(_safe(lambda: service.comps(req.ticker, req.mode)))
    lbo = _data(_safe(lambda: service.lbo(scenario)))
    mna = _data(_safe(lambda: service.mna(scenario))) if scenario.mna else None
    expectations = _data(_safe(lambda: service.expectations(scenario))) or {}
    var = _data(_safe(lambda: service.value_at_risk(req.ticker, req.mode))) or {}
    evt = _data(_safe(lambda: service.tail_risk(req.ticker, req.mode))) or {}
    merton = _data(_safe(lambda: service.merton(req.ticker, req.mode))) or {}
    regime = _data(_safe(lambda: service.regime_view(req.ticker, req.mode))) or {}
    issues, summary = service.quality_for(company)

    def var_row(method: str, confidence: float) -> dict[str, Any]:
        return next((r for r in var.get("table", []) if r["method"] == method and r["confidence"] == confidence), {})

    implied = expectations.get("implied") or {}
    return {
        "page": req.page,
        "company": {
            "ticker": company["ticker"], "name": company["company_name"], "sector": company.get("sector"),
            "industry": company.get("industry"), "currency": currency, "price": company.get("current_price"),
            "market_cap": company.get("market_cap"), "shares_outstanding": company.get("shares_outstanding"),
            "fiscal_period": company.get("period"), "data_status": status,
            "source": (company.get("provenance") or {}).get("origin") or (company.get("provenance") or {}).get("source_name"),
            "retrieved_at": company.get("retrieved_at"),
        },
        "fundamentals": {
            "revenue": company.get("revenue"), "ebitda": company.get("ebitda"), "ebit": company.get("ebit"),
            "net_income": company.get("net_income"), "total_debt": company.get("total_debt"),
            "cash": company.get("cash_and_equivalents"), "book_equity": company.get("book_equity"),
            **{k: actuals.get(k) for k in ("ebitda_margin", "roe", "roic", "ev_ebitda", "pe", "pb", "net_debt_to_ebitda")},
        },
        "history": {k: baseline["history"].get(k) for k in ("years", "revenue_cagr", "margin_average")},
        "valuation_model": baseline["classification"]["intrinsic_model"],
        "assumptions": intrinsic.get("inputs"),
        "wacc_build": baseline["wacc_build"],
        "intrinsic": {k: intrinsic.get(k) for k in ("implied_share_price", "upside", "enterprise_value", "equity_value",
                                                     "net_debt", "terminal_share_of_ev", "justified_pb", "market_pb", "flags")} if intrinsic else None,
        "comps": {
            "primary_label": comps["primary_label"], "implied_mid": comps["implied_range"]["mid"],
            "implied_low": comps["implied_range"]["low"], "implied_high": comps["implied_range"]["high"],
            "peers": [p["ticker"] for p in comps["peers"]],
        } if comps else None,
        "lbo": {
            "irr": lbo["irr"], "moic": lbo["moic"], "entry_multiple": lbo["inputs"]["entry_multiple"],
            "exit_multiple": lbo["inputs"]["exit_multiple"], "entry_leverage": lbo["entry_leverage"],
            "attribution": lbo["attribution"], "flags": [f["message"] for f in lbo["flags"]],
        } if lbo else None,
        "mna": {
            "acquirer": mna["acquirer_ticker"], "target": mna["target_ticker"], "currency": mna["currency"],
            "offer_price": mna["offer_price"], "purchase_price": mna["total_purchase_price"],
            "eps_change_pct": mna["eps_change_pct"], "eps_change_pct_run_rate": mna["eps_change_pct_run_rate"],
            "break_even": mna["break_even_pre_tax_synergy"], "ownership_target": mna["ownership_target"],
            "flags": [f["message"] for f in mna["flags"]],
        } if mna else None,
        "expectations": {
            "narrative": expectations.get("narrative", []), "odds": expectations.get("odds_fundamentals_beat_price"),
            "implied_growth": implied.get("revenue_growth"), "implied_margin": implied.get("ebitda_margin"),
            "implied_return": implied.get("expected_return"), "stance": expectations.get("stance"),
            "historical_cagr": (expectations.get("historical") or {}).get("revenue_cagr"),
            "implied_roe": expectations.get("implied_steady_state_roe"),
        } if expectations else None,
        "risk": {
            "annualized_volatility": var.get("annualized_volatility"),
            "var_95_historical": var_row("historical", 0.95).get("var_1d"),
            "es_95_historical": var_row("historical", 0.95).get("es_1d"),
            "var_99_cornish_fisher": var_row("cornish_fisher", 0.99).get("var_1d"),
            "evt_var_99": (evt.get("levels") or [{}])[0].get("var_1d"), "evt_xi": evt.get("shape_xi"),
            "merton_pd": merton.get("probability_of_default"), "merton_dd": merton.get("distance_to_default"),
            "regime": regime.get("current_regime"), "regimes_supported": regime.get("regimes_supported"),
        },
        "data_quality": {
            "score": summary["score"], "errors": [i["message"] for i in issues if i["severity"] == "ERROR"],
            "warnings": [i["message"] for i in issues if i["severity"] == "WARNING"],
        },
    }


def _sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


class CopilotOrchestrator:
    def providers(self) -> list[LLMProvider]:
        available = {
            "gemini": (os.environ.get("GEMINI_API_KEY"), lambda key: GeminiProvider(key, os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"))),
            "groq": (os.environ.get("GROQ_API_KEY"), lambda key: GroqProvider(key, os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b"))),
        }
        order = [os.environ.get("AI_PROVIDER_PRIMARY", "gemini").lower(), os.environ.get("AI_PROVIDER_FALLBACK", "groq").lower()]
        order += [name for name in available if name not in order]
        result = []
        for name in order:
            key, factory = available.get(name, (None, None))
            if key and factory:
                result.append(factory(key))
        return result

    def configured(self) -> list[str]:
        return [p.name for p in self.providers()]

    @staticmethod
    def _messages(req: CopilotRequest) -> list[ChatMessage]:
        return [*req.history[-10:], ChatMessage(role="user", content=f"[Page: {req.page}] {req.message}")]

    @staticmethod
    def _system(context: dict[str, Any]) -> str:
        return SYSTEM_RULES + "\n--- VALUENGINE CONTEXT ---\n" + json.dumps(service.json_safe(context), indent=1, default=str)

    def answer(self, req: CopilotRequest) -> dict[str, Any]:
        context = build_context(req)
        system, messages = self._system(context), self._messages(req)
        errors: list[str] = []
        for index, provider in enumerate(self.providers()):
            try:
                text = provider.generate(system, messages)
                return {"answer": text, "provider": provider.name, "model": provider.model, "mode": "llm",
                        "is_fallback": index > 0, "errors": errors, "context_ticker": context["company"]["ticker"]}
            except ProviderError as exc:
                logger.warning("Copilot provider failed: %s", exc)
                errors.append(str(exc))
        return {"answer": offline_answer(req.message, context), "provider": "Offline analyst", "model": None,
                "mode": "offline", "is_fallback": bool(errors), "errors": errors, "context_ticker": context["company"]["ticker"]}

    def stream(self, req: CopilotRequest) -> Iterator[str]:
        try:
            context = build_context(req)
        except service.NotFound as exc:
            yield _sse("error", {"message": exc.message})
            yield _sse("done", {})
            return
        system, messages = self._system(context), self._messages(req)
        errors: list[str] = []
        for index, provider in enumerate(self.providers()):
            started = False
            try:
                for chunk in provider.stream(system, messages):
                    if not started:
                        yield _sse("meta", {"provider": provider.name, "model": provider.model, "mode": "llm",
                                            "is_fallback": index > 0, "errors": errors})
                        started = True
                    yield _sse("delta", {"text": chunk})
                if started:
                    yield _sse("done", {})
                    return
                errors.append(f"{provider.name} returned an empty answer.")
            except ProviderError as exc:
                logger.warning("Copilot stream failed: %s", exc)
                errors.append(str(exc))
                if started:
                    yield _sse("error", {"message": f"{provider.name} stopped mid-answer: {exc}"})
                    yield _sse("done", {})
                    return
        yield _sse("meta", {"provider": "Offline analyst", "model": None, "mode": "offline",
                            "is_fallback": bool(errors), "errors": errors})
        text = offline_answer(req.message, context)
        for start in range(0, len(text), 160):
            yield _sse("delta", {"text": text[start:start + 160]})
        yield _sse("done", {})

    def memo(self, scenario: ScenarioRequest) -> dict[str, Any]:
        req = CopilotRequest(message="Write the investment committee memo.", ticker=scenario.ticker, mode=scenario.mode,
                             page="reports", scenario=scenario)
        context = build_context(req)
        prompt = ("Write a concise investment committee memo in markdown with these sections: 1. Summary view, "
                  "2. Valuation (intrinsic value, assumptions, sensitivities), 3. What the market is pricing in, "
                  "4. Relative value (comps), 5. Transaction perspectives (LBO, and M&A if an acquirer is in context), "
                  "6. Key risks, 7. Data caveats. Quote the numbers from the context; do not add facts.")
        generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for provider in self.providers():
            try:
                text = provider.generate(self._system(context), [ChatMessage(role="user", content=prompt)])
                return {"markdown": text, "provider": provider.name, "mode": "llm", "generated_at": generated_at}
            except ProviderError as exc:
                logger.warning("Memo provider failed: %s", exc)
        return {"markdown": offline_memo(context), "provider": "Offline analyst", "mode": "offline", "generated_at": generated_at}


copilot_orchestrator = CopilotOrchestrator()
