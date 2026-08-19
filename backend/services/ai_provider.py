import os
import time
from abc import ABC, abstractmethod
from typing import Any
import requests

from backend.schemas.models import CopilotRequest
from backend.services import valuation_service


class AIProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_message: str) -> tuple[str, str]:
        """Returns (response_text, model_name)."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass


class GeminiProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "gemini-3.5-flash"):
        self.api_key = api_key
        self.model = model

    @property
    def provider_name(self) -> str:
        return "Gemini"

    def generate(self, system_prompt: str, user_message: str) -> tuple[str, str]:
        # Using raw HTTP for maximum control and avoiding heavy SDK init if not needed
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "parts": [{"text": user_message}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2
            }
        }
        
        print(f"provider=gemini model={self.model} endpoint=generativelanguage.googleapis.com request_started=true")
        try:
            resp = requests.post(url, json=payload, timeout=15)
        except requests.Timeout:
            raise Exception("Gemini request timed out (408)")
        except requests.RequestException:
            raise Exception("Gemini network error (503)")
            
        if resp.status_code == 429:
            raise Exception("Gemini API rate limit exceeded (429)")
        elif resp.status_code == 404:
            raise Exception(f"Gemini API 404 NOT_FOUND: Invalid model {self.model} or endpoint")
        elif resp.status_code in {401, 403}:
            raise Exception("Gemini API 401/403: Authentication or configuration error")
        elif resp.status_code == 400:
            raise Exception("Gemini API 400: Malformed request payload")
        elif resp.status_code >= 500:
            raise Exception(f"Gemini API {resp.status_code}: Temporary provider failure")
        elif resp.status_code != 200:
            raise Exception(f"Gemini API {resp.status_code} error")
            
        try:
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return text, self.model
        except (KeyError, IndexError):
            raise Exception("Unexpected response format from Gemini")


class GroqProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "openai/gpt-oss-20b"):
        self.api_key = api_key
        self.model = model

    @property
    def provider_name(self) -> str:
        return "Groq"

    def generate(self, system_prompt: str, user_message: str) -> tuple[str, str]:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.2
        }
        
        print(f"provider=groq model={self.model} endpoint=api.groq.com request_started=true")
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
        except requests.Timeout:
            raise Exception("Groq request timed out (408)")
        except requests.RequestException:
            raise Exception("Groq network error (503)")
            
        if resp.status_code == 429:
            raise Exception("Groq API rate limit exceeded (429)")
        elif resp.status_code == 404:
            raise Exception(f"Groq API 404 NOT_FOUND: Invalid model {self.model} or endpoint")
        elif resp.status_code in {401, 403}:
            raise Exception("Groq API 401/403: Authentication or configuration error")
        elif resp.status_code == 400:
            raise Exception("Groq API 400: Malformed request payload")
        elif resp.status_code >= 500:
            raise Exception(f"Groq API {resp.status_code}: Temporary provider failure")
        elif resp.status_code != 200:
            raise Exception(f"Groq API {resp.status_code} error")
            
        try:
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            return text, self.model
        except (KeyError, IndexError):
            raise Exception("Unexpected response format from Groq")


class CopilotOrchestrator:
    def __init__(self):
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")
        self.groq_key = os.environ.get("GROQ_API_KEY", "")
        self.primary_name = os.environ.get("AI_PROVIDER_PRIMARY", "gemini").lower()
        self.fallback_name = os.environ.get("AI_PROVIDER_FALLBACK", "groq").lower()

    def get_provider(self, name: str) -> AIProvider | None:
        if name == "gemini" and self.gemini_key:
            model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
            return GeminiProvider(self.gemini_key, model)
        elif name == "groq" and self.groq_key:
            model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
            return GroqProvider(self.groq_key, model)
        return None

    def build_system_prompt(self, context_data: dict) -> str:
        import json
        return f"""You are ValuAI, the financial-analysis copilot inside ValuEngine.
You are an institutional financial analyst.

Use only verified ValuEngine context supplied below.
Never fabricate financial values, transactions, market data, calculations, or citations.
If information is unavailable, explicitly say that it is unavailable.

Distinguish between observed data, calculated model outputs, assumptions, and interpretation.
When discussing valuation, explain the drivers rather than merely repeating the output.
When discussing DCF, explain revenue growth, margins, WACC, terminal growth, FCF, terminal value, net debt, resulting equity value.
When discussing Trading Comps, explain peer selection, multiples, median/mean, implied valuation.
When discussing LBO, explain entry valuation, leverage, EBITDA growth, debt paydown, exit multiple, sponsor returns, IRR, MOIC.
When discussing M&A, explain purchase price, financing, premium, consideration mix, EPS accretion/dilution.
When discussing Risk Lab, explain probability, distribution, volatility, VaR/CVaR, tail risk, default risk, regime, sensitivity.

Never give investment advice as certainty.
Use concise but analytical language. Format nicely with markdown.
If a conclusion depends on an assumption, explicitly identify that assumption.

--- VALUENGINE CONTEXT ---
{json.dumps(context_data, indent=2)}
"""

    def gather_context(self, ticker: str, mode: str) -> dict:
        ctx = {}
        # 1. Company Data & Fundamentals
        comp = valuation_service.company(ticker, mode=mode)
        if not comp:
            return {"error": f"Ticker {ticker} not available in {mode} mode"}
        
        ctx["company"] = {
            "ticker": comp.get("ticker"),
            "company_name": comp.get("company_name"),
            "exchange": comp.get("exchange"),
            "sector": comp.get("sector"),
            "industry": comp.get("industry"),
            "currency": comp.get("currency"),
            "current_price": comp.get("current_price"),
            "market_cap": comp.get("market_cap"),
            "shares_outstanding": comp.get("shares_outstanding"),
            "beta": comp.get("beta")
        }
        ctx["fundamentals"] = {
            "revenue": comp.get("revenue"),
            "ebitda": comp.get("ebitda"),
            "ebit": comp.get("ebit"),
            "net_income": comp.get("net_income"),
            "eps": comp.get("eps"),
            "operating_cash_flow": comp.get("operating_cash_flow"),
            "capex": comp.get("capex"),
            "total_debt": comp.get("total_debt"),
            "cash_and_equivalents": comp.get("cash_and_equivalents"),
        }

        # 2. DCF
        dcf_result = valuation_service.run_dcf(comp, 0.07, 0.25, 0.085, 0.025, 5, 0.21, False)
        if dcf_result.get("status") == "VALID":
            ctx["dcf"] = {
                "implied_share_price": dcf_result.get("implied_share_price"),
                "upside_downside_pct": dcf_result.get("upside_downside_pct"),
                "enterprise_value": dcf_result.get("enterprise_value"),
                "equity_value": dcf_result.get("equity_value"),
                "wacc": dcf_result.get("wacc"),
                "terminal_growth_rate": dcf_result.get("terminal_growth_rate")
            }

        # 3. LBO
        lbo_result = valuation_service.run_lbo_model(comp, 10.0, 0.4, 0.2, 0.08, 0.10, 11.0, 0.07, 0.25, 5, 0.21)
        if lbo_result.get("status") == "VALID":
            ctx["lbo"] = {
                "irr": lbo_result.get("irr"),
                "moic": lbo_result.get("moic"),
                "entry_ev": lbo_result.get("entry_ev"),
                "exit_ev": lbo_result.get("exit_ev")
            }

        # 4. Trading Comps
        if mode == "local":
            target_sector = comp.get("sector")
            peer_rows = valuation_service._data_loader.store.get_peers(ticker, sector=target_sector, limit=12)
            if peer_rows:
                comps_result = valuation_service.run_trading_comps(comp, peer_rows)
                if comps_result.get("status") == "VALID":
                    ctx["trading_comps"] = {
                        "peers_count": comps_result.get("peers_count"),
                        "implied_share_price": comps_result.get("implied_share_price"),
                        "median_ev_ebitda": comps_result.get("median_ev_ebitda")
                    }

        # 5. Risk (Merton + Var)
        merton = valuation_service.r_risk_engine.run_merton(comp)
        if merton.get("status") == "VALID":
            ctx["risk_merton"] = {
                "probability_of_default": merton.get("probability_of_default"),
                "distance_to_default": merton.get("distance_to_default")
            }
            
        var_cvar = valuation_service.r_risk_engine.run_var_cvar(comp)
        if var_cvar.get("status") == "VALID":
            ctx["risk_var"] = {
                "historical_var": var_cvar.get("historical_var"),
                "parametric_var": var_cvar.get("parametric_var")
            }

        return ctx

    def process_request(self, payload: CopilotRequest) -> dict[str, Any]:
        primary = self.get_provider(self.primary_name)
        fallback = self.get_provider(self.fallback_name)

        if not primary and not fallback:
            return {
                "status": "UNAVAILABLE",
                "data": {"provider": "NOT_CONFIGURED", "answer": "AI Copilot is not configured. Missing API keys."},
                "warnings": ["AI Copilot is not configured."],
                "errors": [],
                "provenance": {"source": "AI Copilot"}
            }

        context_data = self.gather_context(payload.ticker, mode="local") # Assuming local mode for context for now, or could be passed in request
        system_prompt = self.build_system_prompt(context_data)
        
        user_message = payload.message
        if payload.page_context:
            user_message = f"[Current App Page: {payload.page_context}]\nUser: {user_message}"

        provider_used = ""
        model_used = ""
        answer = ""
        errors = []
        is_fallback = False

        print("COPILOT_REQUEST_RECEIVED")

        if primary:
            print(f"COPILOT_PROVIDER_ATTEMPT={primary.provider_name.lower()}")
            try:
                answer, model_used = primary.generate(system_prompt, user_message)
                provider_used = primary.provider_name
                print(f"COPILOT_PROVIDER_SUCCESS={primary.provider_name.lower()}")
            except Exception as e:
                err_msg = str(e)
                errors.append(err_msg)
                # DO NOT fallback if it's a 404, 401, 403, 400
                if any(c in err_msg for c in ["404", "401", "403", "400"]):
                    pass # Don't fallback on configuration/validation errors
                else:
                    # It's a 429, timeout, or 50x, we can fallback
                    primary = None 
        
        if not answer and fallback and not primary:
            print(f"COPILOT_PROVIDER_ATTEMPT={fallback.provider_name.lower()}")
            try:
                answer, model_used = fallback.generate(system_prompt, user_message)
                provider_used = fallback.provider_name
                is_fallback = True
                print(f"COPILOT_PROVIDER_SUCCESS={fallback.provider_name.lower()}")
            except Exception as e:
                errors.append(str(e))

        if not answer:
            return {
                "status": "ERROR",
                "data": {},
                "warnings": ["AI Copilot is temporarily unavailable"],
                "errors": errors,
                "provenance": {"source": "ValuEngine AI Copilot"}
            }

        return {
            "status": "VALID",
            "data": {
                "answer": answer,
                "provider": provider_used,
                "model": model_used,
                "is_fallback": is_fallback,
                "citations": [],
                "context_used": {
                    "ticker": payload.ticker,
                    "page": payload.page_context,
                    "data_mode": "LOCAL"
                }
            },
            "warnings": [],
            "errors": errors,
            "provenance": {"source": "ValuEngine AI Copilot"}
        }

copilot_orchestrator = CopilotOrchestrator()
