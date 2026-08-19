from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.schemas.models import AnalyticsRequest, CompanyRequest, CopilotRequest, DcfRequest, ExportRequest, LboRequest, MnaRequest
from backend.services import valuation_service as service
from backend.services.ai_provider import copilot_orchestrator

app = FastAPI(
    title="ValuEngine API",
    version="1.0.0",
    description="Transport layer for locked ValuEngine financial engines.",
)

# Allow requests from Vite dev servers on ports 5173, 5174, etc.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def api_health():
    return {
        "status": "VALID",
        "data": {"service": "ValuEngine API"},
        "warnings": [],
        "errors": [],
        "provenance": {"notice": "Financial engines are local"},
    }


@app.get("/api/companies/search")
def search_companies(q: str = "", mode: str = "local", limit: int = 15):
    results = service.search_companies(q, mode=mode, limit=limit)
    return {
        "status": "VALID",
        "data": {"results": results, "count": len(results)},
        "warnings": [],
        "errors": [],
        "provenance": {"mode": mode},
    }


@app.get("/api/company/available")
def available_companies(mode: str = "local"):
    if mode == "local":
        count = service._data_loader.store.get_company_count()
        sample = [c["ticker"] for c in service._data_loader.store.search_companies("", limit=10)]
        return {
            "status": "LOCAL",
            "data": {"tickers": sample, "total_count": count},
            "warnings": [],
            "errors": [],
            "provenance": {"source": "LOCAL_DB", "notice": f"Local database contains {count} companies"},
        }
    provider = service._data_loader.provider
    has_key = bool(provider.api_key)
    cb_active = provider.is_circuit_breaker_active()
    status = "RATE_LIMITED" if cb_active else ("LIVE" if has_key else "DEMO")
    return {
        "status": status,
        "data": {"tickers": ["AAPL", "MSFT", "NVDA"]},
        "warnings": ["Circuit breaker active. Rate limit cooldown in progress."] if cb_active else ([] if has_key else ["Live API not configured."]),
        "errors": [],
        "provenance": {"source": status},
    }


@app.get("/api/company/{ticker}")
def get_company(ticker: str, mode: str = "local"):
    data = service.company(ticker, mode=mode)
    if not data:
        return service.unavailable(ticker, mode=mode)
    prov_type = data.get("_provenance") or data.get("provenance", {}).get("source_type") or ("LOCAL" if mode == "local" else "DEMO")
    if prov_type not in {"LIVE", "LOCAL", "CACHED", "RATE_LIMITED", "DEMO"}:
        prov_type = "LOCAL" if mode == "local" else "DEMO"
    return {
        "status": prov_type,
        "data": service.json_safe(data),
        "warnings": [] if prov_type in {"LIVE", "LOCAL", "CACHED"} else [data.get("provenance", {}).get("notice", "Alpha Vantage unavailable.")],
        "errors": [],
        "provenance": data.get("provenance", {}),
    }


@app.post("/api/dcf/run")
def run_dcf(payload: DcfRequest):
    return service.dcf(payload)


@app.post("/api/dcf/sensitivity")
def run_dcf_sensitivity(payload: DcfRequest):
    return service.dcf_sensitivity(payload)


@app.post("/api/mna/run")
def run_mna(payload: MnaRequest):
    return service.mna(payload)


@app.post("/api/lbo/run")
def run_lbo(payload: LboRequest):
    return service.lbo(payload)


@app.get("/api/comps/trading/{ticker}")
def get_trading_comps(ticker: str, mode: str = "local"):
    return service.trading_comps(ticker, mode=mode)


@app.get("/api/comps/transactions/{ticker}")
def get_transaction_comps(ticker: str, mode: str = "local"):
    return service.transaction_comps(ticker, mode=mode)


@app.post("/api/analytics/monte-carlo")
def monte_carlo(payload: AnalyticsRequest):
    return service.analytics(payload)


@app.post("/api/analytics/risk")
def risk(payload: DcfRequest):
    return service.risk(payload)


@app.get("/api/risk/var/{ticker}")
def risk_var(ticker: str, mode: str = "local"):
    return service.risk_var(ticker, mode=mode)


@app.get("/api/risk/cvar/{ticker}")
def risk_cvar(ticker: str, mode: str = "local"):
    return service.risk_var(ticker, mode=mode)


@app.get("/api/risk/merton/{ticker}")
def risk_merton(ticker: str, mode: str = "local"):
    return service.risk_merton(ticker, mode=mode)


@app.get("/api/risk/regime/{ticker}")
def risk_regime(ticker: str, mode: str = "local"):
    return service.risk_regime(ticker, mode=mode)


@app.get("/api/risk/fama-french/{ticker}")
def risk_fama_french(ticker: str, mode: str = "local"):
    return service.risk_factor_model(ticker, mode=mode)


@app.get("/api/risk/evt/{ticker}")
def risk_evt(ticker: str, mode: str = "local"):
    return service.risk_evt(ticker, mode=mode)


@app.get("/api/risk/copula/{acquirer}/{target}")
def risk_copula(acquirer: str, target: str, mode: str = "local"):
    return service.risk_copula(acquirer, target, mode=mode)


@app.get("/api/risk/valuation-confidence/{ticker}")
def valuation_confidence(ticker: str, mode: str = "local"):
    return service.valuation_confidence(ticker, mode=mode)


@app.post("/api/risk/monte-carlo/{ticker}")
def risk_monte_carlo_post(ticker: str, payload: AnalyticsRequest):
    payload.ticker = ticker
    return service.analytics(payload)


@app.post("/api/risk/sensitivity/{ticker}")
def risk_sensitivity_post(ticker: str, payload: DcfRequest):
    payload.ticker = ticker
    return service.dcf_sensitivity(payload)


@app.get("/api/risk/monte-carlo/{ticker}")
def risk_monte_carlo_get(ticker: str, mode: str = "local"):
    payload = AnalyticsRequest(ticker=ticker, mode=mode)
    return service.analytics(payload)


@app.get("/api/risk/sensitivity/{ticker}")
def risk_sensitivity_get(ticker: str, mode: str = "local"):
    payload = DcfRequest(ticker=ticker, mode=mode)
    return service.dcf_sensitivity(payload)


@app.get("/api/model-health/{ticker}")
def model_health(ticker: str, acquirer_ticker: str = "MSFT", mode: str = "local"):
    return service.health(ticker, acquirer_ticker, mode=mode)


@app.get("/api/data-quality/{ticker}")
def data_quality(ticker: str, mode: str = "local"):
    return service.data_quality(ticker, mode=mode)


@app.post("/api/reports/excel")
def export_excel(payload: ExportRequest):
    path = service.export_excel(payload.target_ticker, payload.acquirer_ticker, mode=payload.mode)
    if path is None:
        raise HTTPException(status_code=404, detail="Company data unavailable; Excel export was not generated.")
    return FileResponse(
        path,
        filename=f"ValuEngine_{payload.target_ticker.upper()}_Report.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.post("/api/ai/copilot")
def run_copilot(payload: CopilotRequest):
    print("COPILOT_ROUTE_HIT: POST /api/ai/copilot received request.")
    return copilot_orchestrator.process_request(payload)
