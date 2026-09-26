"""ValuEngine HTTP API.

Every JSON route returns the envelope {status, data, warnings, errors, provenance}; `data` is typed
by the response models in backend/schemas/responses.py (the source of the frontend's TS types).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from typing import Annotated
import os
from pathlib import Path
import threading

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Path as PathParam, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

from backend.schemas import responses as r  # noqa: E402
from backend.schemas.models import CopilotRequest, DataMode, MonteCarloRequest, ScenarioRequest  # noqa: E402
from backend.security import is_authorized, rate_limit  # noqa: E402
from backend.services import valuation_service as service  # noqa: E402
from backend.services.ai_provider import copilot_orchestrator  # noqa: E402
from mna_lbo_engine.modules.snapshot import import_snapshot, snapshot_available  # noqa: E402

logging.basicConfig(level=os.environ.get("VALUENGINE_LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("valuengine.api")
TICKER = r"^[A-Za-z0-9.\-&^]{1,20}$"
Ticker = Annotated[str, PathParam(pattern=TICKER)]


def bootstrap_data() -> None:
    store = service.store()
    if store.get_company_count() == 0 and snapshot_available():
        counts = import_snapshot(store)
        logger.info("Local store was empty; imported the bundled snapshot: %s", counts)


@asynccontextmanager
async def lifespan(_: FastAPI):
    bootstrap_data()
    if os.environ.get("VALUENGINE_WARMUP", "1") == "1":
        threading.Thread(target=service.warm_up, name="valuengine-warmup", daemon=True).start()
    yield


app = FastAPI(
    title="ValuEngine API",
    version=service.VERSION,
    description="Valuation, deal modelling and risk analytics over a local US + India equity dataset.",
    lifespan=lifespan,
)
origins = [o.strip() for o in os.environ.get(
    "VALUENGINE_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type", "Authorization", "X-API-Key"])


@app.middleware("http")
async def authenticate(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.url.path != "/api/health" and request.method != "OPTIONS":
        if not is_authorized(request):
            return JSONResponse(status_code=401, content=service.envelope("ERROR", errors=["Missing or invalid API token."]))
    return await call_next(request)


@app.exception_handler(service.NotFound)
async def not_found(_: Request, exc: service.NotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content=exc.as_envelope())


@app.exception_handler(RequestValidationError)
async def invalid_request(_: Request, exc: RequestValidationError) -> JSONResponse:
    messages = [f"{'.'.join(str(p) for p in e['loc'][1:]) or 'request'}: {e['msg']}" for e in exc.errors()]
    return JSONResponse(status_code=422, content=service.envelope("INVALID", errors=messages))


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=service.envelope("ERROR", errors=[str(exc.detail)]))


@app.exception_handler(Exception)
async def unexpected(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error")
    return JSONResponse(status_code=500, content=service.envelope("ERROR", errors=["Internal error; see server logs."]))


ModeParam = Query("local", description="local = SQLite store; live = Alpha Vantage with local fallback")


# ----------------------------------------------------------------------------- platform
@app.get("/api/health")
def api_health() -> dict:
    return service.envelope("VALID", {"service": "ValuEngine API", "version": service.VERSION})


@app.get("/api/meta", response_model=r.Envelope[r.Meta])
def api_meta():
    return service.meta(copilot_orchestrator.configured())


@app.get("/api/companies/search", response_model=r.Envelope[r.SearchData])
def search_companies(q: str = Query("", max_length=60), limit: int = Query(15, ge=1, le=50)):
    return service.search(q, limit)


@app.get("/api/company/{ticker}", response_model=r.Envelope[r.Company])
def get_company(ticker: Ticker, mode: DataMode = ModeParam):
    return service.company_view(ticker, mode)


@app.get("/api/company/{ticker}/baseline", response_model=r.Envelope[r.Baseline])
def get_baseline(ticker: Ticker, mode: DataMode = ModeParam):
    return service.baseline_view(ticker, mode)


@app.get("/api/company/{ticker}/history", response_model=r.Envelope[r.HistoryResult])
def get_history(ticker: Ticker):
    return service.history_view(ticker)


@app.get("/api/data-quality/{ticker}", response_model=r.Envelope[r.DataQualityResult])
def data_quality(ticker: Ticker, mode: DataMode = ModeParam):
    return service.data_quality(ticker, mode)


# ----------------------------------------------------------------------------- valuation & deals
@app.post("/api/valuation/intrinsic", response_model=r.Envelope[r.IntrinsicResult])
def intrinsic(req: ScenarioRequest):
    return service.intrinsic(req)


@app.post("/api/valuation/sensitivity", response_model=r.Envelope[r.SensitivityResult])
def sensitivity(req: ScenarioRequest):
    return service.sensitivity(req)


@app.post("/api/mna/run", response_model=r.Envelope[r.MnaResult])
def run_mna(req: ScenarioRequest):
    return service.mna(req)


@app.post("/api/lbo/run", response_model=r.Envelope[r.LboResult])
def run_lbo(req: ScenarioRequest):
    return service.lbo(req)


@app.post("/api/lbo/stress", response_model=r.Envelope[r.StressResult])
def lbo_stress(req: ScenarioRequest):
    return service.lbo_stress(req)


@app.get("/api/comps/{ticker}", response_model=r.Envelope[r.CompsResult])
def trading_comps(ticker: Ticker, mode: DataMode = ModeParam):
    return service.comps(ticker, mode)


@app.get("/api/comps/{ticker}/transactions", response_model=r.Envelope[dict])
def transaction_comps(ticker: Ticker, mode: DataMode = ModeParam):
    return service.transaction_comps(ticker, mode)


@app.post("/api/model-health", response_model=r.Envelope[r.HealthResult])
def model_health(req: ScenarioRequest):
    return service.health(req)


# ----------------------------------------------------------------------------- expectations lab
@app.post("/api/expectations", response_model=r.Envelope[r.ExpectationsResult])
def expectations(req: ScenarioRequest):
    return service.expectations(req)


@app.get("/api/expectations/universe", response_model=r.Envelope[r.RadarResult])
def expectations_universe():
    return service.radar()


# ----------------------------------------------------------------------------- risk lab
@app.post("/api/risk/monte-carlo", response_model=r.Envelope[r.MonteCarloResult],
          dependencies=[Depends(rate_limit("simulation", 60))])
def monte_carlo(req: MonteCarloRequest):
    return service.monte_carlo(req)


@app.get("/api/risk/var/{ticker}", response_model=r.Envelope[r.VarResult])
def risk_var(ticker: Ticker, mode: DataMode = ModeParam):
    return service.value_at_risk(ticker, mode)


@app.get("/api/risk/evt/{ticker}", response_model=r.Envelope[r.EvtResult])
def risk_evt(ticker: Ticker, mode: DataMode = ModeParam):
    return service.tail_risk(ticker, mode)


@app.get("/api/risk/regime/{ticker}", response_model=r.Envelope[r.RegimeResult])
def risk_regime(ticker: Ticker, mode: DataMode = ModeParam):
    return service.regime_view(ticker, mode)


@app.get("/api/risk/factors/{ticker}", response_model=r.Envelope[r.FactorResult])
def risk_factors(ticker: Ticker, mode: DataMode = ModeParam):
    return service.factors(ticker, mode)


@app.get("/api/risk/merton/{ticker}", response_model=r.Envelope[r.MertonResult])
def risk_merton(ticker: Ticker, mode: DataMode = ModeParam):
    return service.merton(ticker, mode)


@app.get("/api/risk/copula/{acquirer}/{target}", response_model=r.Envelope[r.CopulaResult])
def risk_copula(acquirer: Ticker, target: Ticker, mode: DataMode = ModeParam):
    return service.copula(acquirer, target, mode)


@app.post("/api/risk/confidence", response_model=r.Envelope[r.ConfidenceResult])
def risk_confidence(req: ScenarioRequest):
    return service.valuation_confidence(req)


# ----------------------------------------------------------------------------- outputs
@app.post("/api/reports/excel", dependencies=[Depends(rate_limit("export", 30))])
def export_excel(req: ScenarioRequest) -> Response:
    content, filename = service.excel(req)
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.post("/api/ai/copilot", response_model=r.Envelope[r.CopilotResult], dependencies=[Depends(rate_limit("copilot", 20))])
def copilot(req: CopilotRequest):
    result = copilot_orchestrator.answer(req)
    return service.envelope("VALID", result, warnings=result["errors"])


@app.post("/api/ai/copilot/stream", dependencies=[Depends(rate_limit("copilot", 20))])
def copilot_stream(req: CopilotRequest) -> StreamingResponse:
    return StreamingResponse(copilot_orchestrator.stream(req), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/ai/memo", response_model=r.Envelope[r.MemoResult], dependencies=[Depends(rate_limit("copilot", 20))])
def investment_memo(req: ScenarioRequest):
    return service.envelope("VALID", copilot_orchestrator.memo(req))
