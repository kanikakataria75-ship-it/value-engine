"""Service layer between the HTTP API and the financial engines.

Responsibilities: load company data with honest provenance, resolve the analyst's scenario on top
of the company baseline, call the engines, cache heavy universe-level analytics, and wrap every
result in the standard envelope {status, data, warnings, errors, provenance}.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import fields as dataclass_fields
from datetime import datetime, timezone
import logging
import math
import os
import threading
from typing import Any, Callable

import numpy as np

from mna_lbo_engine.config import market_parameters
from mna_lbo_engine.modules.assumptions import build_baseline, history_metrics
from mna_lbo_engine.modules.common import country_of, is_balance_sheet_financial
from mna_lbo_engine.modules.comps_engine import run_trading_comps, run_transaction_comps, select_peers
from mna_lbo_engine.modules.data_loader import FinancialDataLoader
from mna_lbo_engine.modules.data_quality_engine import run_data_quality_checks, summarize_quality
from mna_lbo_engine.modules.dcf_engine import DcfInputs, run_dcf, sensitivity_grids
from mna_lbo_engine.modules.excel_exporter import build_workbook
from mna_lbo_engine.modules.expectations import expectations_analysis, financial_expectations, radar_row, radar_summary
from mna_lbo_engine.modules.financials_engine import ExcessReturnInputs, excess_return_sensitivity, run_excess_return
from mna_lbo_engine.modules.fx import FxConverter
from mna_lbo_engine.modules.lbo_engine import LboInputs, run_lbo_model
from mna_lbo_engine.modules.local_financial_store import LocalFinancialStore
from mna_lbo_engine.modules.ma_engine import MnaInputs, run_ma_model
from mna_lbo_engine.modules.model_health import evaluate_model_health, scenario_scorecard
from mna_lbo_engine.modules.risk import confidence as confidence_engine
from mna_lbo_engine.modules.risk import credit, dependence, market_risk, regime, simulation, stress
from mna_lbo_engine.modules.risk.factors import FactorModel, build_price_panel

from backend.schemas.models import MonteCarloRequest, ScenarioRequest

logger = logging.getLogger(__name__)
VERSION = "2.0.0"

_loader = FinancialDataLoader()


def store() -> LocalFinancialStore:
    return _loader.store


# ----------------------------------------------------------------------------- envelopes
def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return [json_safe(v) for v in value.tolist()]
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    return value


def envelope(status: str, data: Any = None, warnings: list[str] | None = None, errors: list[str] | None = None,
             provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"status": status, "data": json_safe(data) if data is not None else None,
            "warnings": warnings or [], "errors": errors or [], "provenance": provenance}


def from_result(result: dict[str, Any], provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    status = result.get("status", "ERROR")
    if status in {"INVALID", "UNAVAILABLE", "ERROR"}:
        return envelope(status, errors=[result.get("message") or "Unavailable."], provenance=provenance)
    data = {k: v for k, v in result.items() if k not in {"status", "message", "warnings"}}
    return envelope(status, data, warnings=result.get("warnings") or [], provenance=provenance)


class NotFound(Exception):
    def __init__(self, status: str, message: str, provenance: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status, self.message, self.provenance = status, message, provenance

    def as_envelope(self) -> dict[str, Any]:
        return envelope(self.status, errors=[self.message], provenance=self.provenance)


# ----------------------------------------------------------------------------- caches
_lock = threading.RLock()
_memo: OrderedDict[Any, tuple[Any, Any]] = OrderedDict()
_MEMO_SIZE = 512


def _signature() -> tuple:
    return store().data_signature()


def cached(key: Any, compute: Callable[[], Any]) -> Any:
    signature = _signature()
    with _lock:
        hit = _memo.get(key)
        if hit and hit[0] == signature:
            _memo.move_to_end(key)
            return hit[1]
    value = compute()
    with _lock:
        _memo[key] = (signature, value)
        _memo.move_to_end(key)
        while len(_memo) > _MEMO_SIZE:
            _memo.popitem(last=False)
    return value


def reset_caches() -> None:
    with _lock:
        _memo.clear()


def factor_model() -> FactorModel:
    def build() -> FactorModel:
        panel = build_price_panel(store().get_price_panel())
        return FactorModel(panel, {c["ticker"]: c for c in store().list_company_rows()})
    return cached(("factor_model",), build)


# ----------------------------------------------------------------------------- loading
def load(ticker: str, mode: str = "local") -> tuple[dict[str, Any], str]:
    company, status, notice = _loader.fetch_company(ticker, data_mode=mode)
    if company is None:
        raise NotFound("UNAVAILABLE", notice or f"{ticker} is unavailable.")
    if notice:
        company.setdefault("provenance", {})["notice"] = company["provenance"].get("notice") or notice
    return company, status


def _company_key(company: dict[str, Any]) -> tuple:
    return (company["ticker"], company.get("current_price"), company.get("retrieved_at"))


def baseline_for(company: dict[str, Any]) -> dict[str, Any]:
    def compute() -> dict[str, Any]:
        beta = factor_model().regression_beta(company["ticker"], (company.get("currency") or "USD").upper())
        return build_baseline(company, store().get_history(company["ticker"]), beta)
    return cached(("baseline",) + _company_key(company), compute)


def quality_for(company: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    issues = run_data_quality_checks(company)
    return issues, summarize_quality(company, issues)


def company_view(ticker: str, mode: str) -> dict[str, Any]:
    company, status = load(ticker, mode)
    issues, summary = quality_for(company)
    data = {**company, "country": country_of(company), "balance_sheet_financial": is_balance_sheet_financial(company),
            "quality": summary, "issues": issues}
    warnings = [i["message"] for i in issues if i["severity"] == "WARNING"]
    return envelope(status, data, warnings=warnings, provenance=company.get("provenance"))


def baseline_view(ticker: str, mode: str) -> dict[str, Any]:
    company, _ = load(ticker, mode)
    return envelope("VALID", baseline_for(company), provenance=company.get("provenance"))


def history_view(ticker: str) -> dict[str, Any]:
    rows = store().get_history(ticker.upper())
    if not rows:
        return envelope("UNAVAILABLE", errors=[f"No fundamentals history stored for {ticker.upper()}."])
    return envelope("VALID", {"rows": rows, "metrics": history_metrics(rows)})


def search(query: str, limit: int) -> dict[str, Any]:
    results = store().search_companies(query, limit=limit)
    return envelope("VALID", {"results": results, "count": len(results)})


def meta(llm_providers: list[str]) -> dict[str, Any]:
    stats = store().get_stats()
    fx = []
    for currency in stats["companies_by_currency"]:
        if currency and currency != "USD":
            row = store().get_fx_rate(f"USD{currency}")
            if row:
                fx.append({"pair": row["pair"], "rate": row["rate"], "date": row["date"], "source": row.get("source")})
    return envelope("VALID", {
        **stats, "fx": fx, "version": VERSION, "llm_providers": llm_providers,
        "live_provider_configured": bool(_loader.provider.api_key),
        "auth_required": bool(os.environ.get("VALUENGINE_API_TOKEN")),
    })


# ----------------------------------------------------------------------------- scenario resolution
def _merge(defaults: dict[str, Any], overrides: Any, allowed: set[str]) -> dict[str, Any]:
    merged = {k: v for k, v in defaults.items() if k in allowed}
    for key, value in (overrides.model_dump() if overrides is not None else {}).items():
        if value is not None and key in allowed:
            merged[key] = value
    return merged


def _names(cls: type) -> set[str]:
    return {f.name for f in dataclass_fields(cls)}


def dcf_inputs(baseline: dict[str, Any], req: ScenarioRequest) -> DcfInputs:
    return DcfInputs(**_merge(baseline["dcf"], req.dcf, _names(DcfInputs)))


def excess_return_inputs(baseline: dict[str, Any], req: ScenarioRequest) -> ExcessReturnInputs | None:
    if not baseline.get("excess_return"):
        return None
    return ExcessReturnInputs(**_merge(baseline["excess_return"], req.excess_return, _names(ExcessReturnInputs)))


def lbo_inputs(baseline: dict[str, Any], req: ScenarioRequest) -> LboInputs | None:
    if not baseline.get("lbo"):
        return None
    return LboInputs(**_merge(baseline["lbo"], req.lbo, _names(LboInputs)))


def mna_inputs(baseline: dict[str, Any], req: ScenarioRequest) -> MnaInputs:
    overrides = req.mna.model_dump(exclude={"acquirer_ticker"}) if req.mna else {}
    values = {k: v for k, v in overrides.items() if v is not None}
    values.setdefault("offer_premium_pct", baseline["mna"]["offer_premium_pct"])
    return MnaInputs(**values)


# ----------------------------------------------------------------------------- engines
def _intrinsic(company: dict[str, Any], baseline: dict[str, Any], req: ScenarioRequest) -> dict[str, Any]:
    if baseline["classification"]["intrinsic_model"] == "excess_return":
        inputs = excess_return_inputs(baseline, req)
        if inputs is None:
            return {"status": "UNAVAILABLE", "message": "ROE is not meaningful (book equity or net income missing)."}
        return run_excess_return(company, inputs)
    return run_dcf(company, dcf_inputs(baseline, req))


def intrinsic(req: ScenarioRequest) -> dict[str, Any]:
    company, _ = load(req.ticker, req.mode)
    return from_result(_intrinsic(company, baseline_for(company), req), company.get("provenance"))


def sensitivity(req: ScenarioRequest) -> dict[str, Any]:
    company, _ = load(req.ticker, req.mode)
    baseline = baseline_for(company)
    if baseline["classification"]["intrinsic_model"] == "excess_return":
        inputs = excess_return_inputs(baseline, req)
        if inputs is None:
            return envelope("UNAVAILABLE", errors=["ROE is not meaningful for this company."])
        result = excess_return_sensitivity(company, inputs)
        result["method"] = "excess_return"
    else:
        result = sensitivity_grids(company, dcf_inputs(baseline, req))
        result["method"] = "dcf"
    return from_result(result, company.get("provenance"))


def mna(req: ScenarioRequest) -> dict[str, Any]:
    if req.mna is None:
        return envelope("INVALID", errors=["Choose an acquirer to run the accretion / dilution model."])
    target, _ = load(req.ticker, req.mode)
    acquirer, _ = load(req.mna.acquirer_ticker, req.mode)
    result = run_ma_model(acquirer, target, mna_inputs(baseline_for(target), req), FxConverter(store()))
    return from_result(result, target.get("provenance"))


def lbo(req: ScenarioRequest) -> dict[str, Any]:
    company, _ = load(req.ticker, req.mode)
    inputs = lbo_inputs(baseline_for(company), req)
    if inputs is None:
        return envelope("INVALID", errors=["An LBO is not applicable: the company is a balance-sheet financial or has no positive EBITDA."],
                        provenance=company.get("provenance"))
    return from_result(run_lbo_model(company, inputs), company.get("provenance"))


def lbo_stress(req: ScenarioRequest) -> dict[str, Any]:
    company, _ = load(req.ticker, req.mode)
    inputs = lbo_inputs(baseline_for(company), req)
    if inputs is None:
        return envelope("INVALID", errors=["An LBO is not applicable to this company."])
    return from_result(stress.lbo_stress(company, inputs), company.get("provenance"))


def _comps_result(company: dict[str, Any]) -> dict[str, Any]:
    def compute() -> dict[str, Any]:
        candidates = store().get_peer_candidates(company["ticker"], company.get("sector"))
        return run_trading_comps(company, select_peers(company, candidates, store().to_usd))
    return cached(("comps",) + _company_key(company), compute)


def comps(ticker: str, mode: str) -> dict[str, Any]:
    company, _ = load(ticker, mode)
    return from_result(_comps_result(company), company.get("provenance"))


def transaction_comps(ticker: str, mode: str) -> dict[str, Any]:
    company, _ = load(ticker, mode)
    return from_result(run_transaction_comps(company, []), company.get("provenance"))


def _monte_carlo(company: dict[str, Any], baseline: dict[str, Any], req: ScenarioRequest,
                 iterations: int = 5000, seed: int = 2024) -> dict[str, Any]:
    if baseline["classification"]["intrinsic_model"] != "dcf":
        return {"status": "UNAVAILABLE", "message": "Monte Carlo simulation runs on the cash-flow DCF, which does not apply to banks and insurers."}
    return simulation.run_monte_carlo(company, dcf_inputs(baseline, req), baseline["history"], iterations, seed)


def monte_carlo(req: MonteCarloRequest) -> dict[str, Any]:
    company, _ = load(req.ticker, req.mode)
    return from_result(_monte_carlo(company, baseline_for(company), req, req.iterations, req.seed), company.get("provenance"))


def _price_model(ticker: str, mode: str, name: str, fn: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    company, _ = load(ticker, mode)
    result = cached((name,) + _company_key(company), lambda: fn(company))
    return from_result(result, company.get("provenance"))


def value_at_risk(ticker: str, mode: str) -> dict[str, Any]:
    return _price_model(ticker, mode, "var", lambda c: market_risk.value_at_risk(c["historical_prices"]))


def tail_risk(ticker: str, mode: str) -> dict[str, Any]:
    return _price_model(ticker, mode, "evt", lambda c: market_risk.tail_risk_evt(c["historical_prices"]))


def regime_view(ticker: str, mode: str) -> dict[str, Any]:
    return _price_model(ticker, mode, "regime", lambda c: regime.regime_analysis(c["historical_prices"]))


def merton(ticker: str, mode: str) -> dict[str, Any]:
    return _price_model(ticker, mode, "merton", lambda c: credit.merton_analysis(c, c["historical_prices"]))


def factors(ticker: str, mode: str) -> dict[str, Any]:
    return _price_model(ticker, mode, "factors", lambda c: factor_model().regression(c["ticker"], c))


def copula(acquirer: str, target: str, mode: str) -> dict[str, Any]:
    a, _ = load(acquirer, mode)
    t, _ = load(target, mode)
    if a["ticker"] == t["ticker"]:
        return envelope("INVALID", errors=["Choose two different companies."])
    result = cached(("copula",) + _company_key(a) + _company_key(t),
                    lambda: dependence.copula_analysis(a["historical_prices"], t["historical_prices"], a["ticker"], t["ticker"]))
    return from_result(result, t.get("provenance"))


def valuation_confidence(req: ScenarioRequest) -> dict[str, Any]:
    company, _ = load(req.ticker, req.mode)
    baseline = baseline_for(company)
    _, summary = quality_for(company)
    intrinsic_result = _intrinsic(company, baseline, req)
    mc = _monte_carlo(company, baseline, req, iterations=3000)
    comps_result = _comps_result(company)
    usable = intrinsic_result.get("status") in {"VALID", "REVIEW_REQUIRED"}
    result = confidence_engine.valuation_confidence(
        summary, mc if mc.get("status") == "VALID" else None,
        intrinsic_result.get("implied_share_price") if usable else None,
        comps_result.get("implied_share_price_median") if comps_result.get("status") == "VALID" else None,
        intrinsic_result.get("terminal_share_of_ev") if usable else None,
        baseline["history"].get("years", 0), len(company.get("historical_prices") or []),
    )
    return from_result(result, company.get("provenance"))


def expectations(req: ScenarioRequest) -> dict[str, Any]:
    company, _ = load(req.ticker, req.mode)
    baseline = baseline_for(company)
    if baseline["classification"]["intrinsic_model"] == "excess_return":
        inputs = excess_return_inputs(baseline, req)
        result = financial_expectations(company, inputs) if inputs else {"status": "UNAVAILABLE", "message": "ROE unavailable."}
    else:
        result = expectations_analysis(company, dcf_inputs(baseline, req), baseline["history"])
    return from_result(result, company.get("provenance"))


def radar() -> dict[str, Any]:
    def compute() -> dict[str, Any]:
        model = factor_model()
        histories = store().get_all_history()
        usd_rates = store().latest_usd_rates()
        rows = []
        for company in store().list_company_rows():
            beta = model.regression_beta(company["ticker"], (company.get("currency") or "USD").upper())
            baseline = build_baseline(company, histories.get(company["ticker"]), beta)
            rate = usd_rates.get((company.get("currency") or "USD").upper())
            cap = company.get("market_cap")
            rows.append({**radar_row(company, baseline), "market_cap_usd": cap / rate if cap and rate else None})
        return {
            "rows": rows,
            "summary": radar_summary(rows),
            "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "methodology": "For every company, the revenue growth that equates the baseline DCF with today's price "
                           "(implied growth) vs. its historical CAGR; for banks and insurers, the ROE implied by the "
                           "price-to-book ratio vs. current ROE.",
        }
    return envelope("VALID", cached(("radar",), compute))


def health(req: ScenarioRequest) -> dict[str, Any]:
    company, _ = load(req.ticker, req.mode)
    baseline = baseline_for(company)
    issues, _ = quality_for(company)
    intrinsic_result = _intrinsic(company, baseline, req)
    lbo_in = lbo_inputs(baseline, req)
    lbo_result = run_lbo_model(company, lbo_in) if lbo_in else None
    mna_result = None
    if req.mna:
        acquirer, _ = load(req.mna.acquirer_ticker, req.mode)
        mna_result = run_ma_model(acquirer, company, mna_inputs(baseline, req), FxConverter(store()))
    name = "DCF" if baseline["classification"]["intrinsic_model"] == "dcf" else "EXCESS_RETURN"
    report = evaluate_model_health({name: intrinsic_result, "M&A": mna_result, "LBO": lbo_result}, issues)
    data = {**report, "scorecard": scenario_scorecard(intrinsic_result, mna_result, lbo_result),
            "acquirer_ticker": req.mna.acquirer_ticker if req.mna else None}
    return envelope(report["status"], data, provenance=company.get("provenance"))


def data_quality(ticker: str, mode: str) -> dict[str, Any]:
    company, _ = load(ticker, mode)
    issues, summary = quality_for(company)
    return envelope(summary["status"], {"issues": issues, "summary": summary},
                    warnings=[i["message"] for i in issues if i["severity"] == "WARNING"],
                    errors=[i["message"] for i in issues if i["severity"] == "ERROR"],
                    provenance=company.get("provenance"))


def excel(req: ScenarioRequest) -> tuple[bytes, str]:
    company, _ = load(req.ticker, req.mode)
    baseline = baseline_for(company)
    issues, _ = quality_for(company)
    payload: dict[str, Any] = {
        "company": {k: v for k, v in company.items() if k != "historical_prices"},
        "currency": (company.get("currency") or "USD").upper(),
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "baseline_notes": baseline["notes"],
        "data_issues": [i for i in issues if i["severity"] != "INFO"],
    }
    intrinsic_result = _intrinsic(company, baseline, req)
    usable = intrinsic_result.get("status") in {"VALID", "REVIEW_REQUIRED"}
    if usable:
        payload["intrinsic_result"] = intrinsic_result
        key = "dcf" if intrinsic_result.get("method") == "dcf" else "excess_return"
        payload[key] = {"inputs": intrinsic_result["inputs"], "result": intrinsic_result}
        grids = (sensitivity_grids(company, dcf_inputs(baseline, req)) if key == "dcf"
                 else excess_return_sensitivity(company, excess_return_inputs(baseline, req)))
        payload["sensitivity"] = grids
    lbo_in = lbo_inputs(baseline, req)
    if lbo_in:
        lbo_result = run_lbo_model(company, lbo_in)
        if lbo_result.get("status") in {"VALID", "REVIEW_REQUIRED"}:
            payload["lbo"] = {"result": lbo_result}
    if req.mna:
        acquirer, _ = load(req.mna.acquirer_ticker, req.mode)
        mna_result = run_ma_model(acquirer, company, mna_inputs(baseline, req), FxConverter(store()))
        if mna_result.get("status") in {"VALID", "REVIEW_REQUIRED"}:
            payload["mna"] = {"result": mna_result, "acquirer": acquirer, "target": company}
    comps_result = _comps_result(company)
    if comps_result.get("status") == "VALID":
        payload["comps"] = comps_result
    return build_workbook(payload), f"ValuEngine_{company['ticker']}_{datetime.now().strftime('%Y%m%d')}.xlsx"


def market_params(currency: str) -> dict[str, Any]:
    return market_parameters(currency).as_dict()


def warm_up() -> None:
    """Build the factor model and the universe radar in the background after startup."""
    try:
        factor_model()
        radar()
        logger.info("Analytics caches warmed up.")
    except Exception:  # warm-up is best-effort; requests will compute on demand
        logger.exception("Cache warm-up failed")
