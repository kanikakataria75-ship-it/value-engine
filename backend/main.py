from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.schemas.models import AnalyticsRequest, CompanyRequest, DcfRequest, ExportRequest, LboRequest, MnaRequest
from backend.services import valuation_service as service

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


@app.get("/api/company/available")
def available_companies():
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
def get_company(ticker: str):
    data = service.company(ticker)
    if not data:
        return service.unavailable(ticker)
    prov_type = data.get("_provenance") or data.get("provenance", {}).get("source_type") or "DEMO"
    if prov_type not in {"LIVE", "CACHED", "RATE_LIMITED", "DEMO"}:
        prov_type = "DEMO"
    return {
        "status": prov_type,
        "data": service.json_safe(data),
        "warnings": [] if prov_type in {"LIVE", "CACHED"} else [data.get("provenance", {}).get("notice", "Alpha Vantage unavailable.")],
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
def get_trading_comps(ticker: str):
    return service.trading_comps(ticker)


@app.get("/api/comps/transactions/{ticker}")
def get_transaction_comps(ticker: str):
    return service.transaction_comps(ticker)


@app.post("/api/analytics/monte-carlo")
def monte_carlo(payload: AnalyticsRequest):
    return service.analytics(payload)


@app.post("/api/analytics/risk")
def risk(payload: DcfRequest):
    return service.risk(payload)


@app.get("/api/model-health/{ticker}")
def model_health(ticker: str, acquirer_ticker: str = "MSFT"):
    return service.health(ticker, acquirer_ticker)


@app.get("/api/data-quality/{ticker}")
def data_quality(ticker: str):
    return service.data_quality(ticker)


@app.post("/api/reports/excel")
def export_excel(payload: ExportRequest):
    path = service.export_excel(payload.target_ticker, payload.acquirer_ticker)
    if path is None:
        raise HTTPException(status_code=404, detail="Company data unavailable; Excel export was not generated.")
    return FileResponse(
        path,
        filename=f"ValuEngine_{payload.target_ticker.upper()}_Report.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
