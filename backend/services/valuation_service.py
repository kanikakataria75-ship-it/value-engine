"""Thin, non-financial adapter over the locked ValuEngine engines."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import math
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np
import pandas as pd

from mna_lbo_engine.config import PRESET_FINANCIALS
from mna_lbo_engine.modules.comps_engine import run_trading_comps, run_transaction_comps
from mna_lbo_engine.modules.data_quality_engine import run_data_quality_checks
from mna_lbo_engine.modules.dcf_engine import run_dcf
from mna_lbo_engine.modules.excel_exporter import ExcelReportExporter
from mna_lbo_engine.modules.lbo_engine import run_lbo_model
from mna_lbo_engine.modules.ma_engine import run_ma_model
from mna_lbo_engine.modules.model_health import calculate_deal_quality, evaluate_model_health
from mna_lbo_engine.modules.risk_engine import run_dcf_monte_carlo, run_stress_test
from mna_lbo_engine.modules.data_loader import FinancialDataLoader
from mna_lbo_engine.modules.alpha_vantage_provider import AlphaVantageError, AlphaVantageRateLimited

from mna_lbo_engine.modules import r_risk_engine


_data_loader = FinancialDataLoader()


def company(ticker: str, mode: str = "local") -> dict[str, Any] | None:
    symbol = ticker.strip().upper()
    if not symbol:
        return None

    is_rate_limited = False
    fallback_reason = "Alpha Vantage unavailable."

    try:
        try:
            result = _data_loader.fetch_company_financials(symbol, data_mode=mode)
        except TypeError:
            result = _data_loader.fetch_company_financials(symbol)

        if result is not None:
            quality_issues = run_data_quality_checks(result)
            if any(issue["severity"] == "HARD ERROR" for issue in quality_issues):
                raise AlphaVantageError("Alpha Vantage data did not pass the existing data-quality gate.")
            result["data_quality_issues"] = quality_issues
            if mode == "local":
                prov = result.setdefault("provenance", {})
                prov.setdefault("source", "LOCAL_DB")
                prov.setdefault("source_type", "LOCAL_DB")
                prov.setdefault("provenance", "LIVE")
                prov.setdefault("source_name", "ValuEngine Local Store (389 Companies)")
                prov.setdefault("notice", "Offline Institutional SQLite Dataset · Zero Latency")
                result["_provenance"] = "LIVE"
            return result
        elif mode == "local":
            return None
    except AlphaVantageRateLimited as exc:
        fallback_reason = str(exc)
        is_rate_limited = True
    except AlphaVantageError as exc:
        fallback_reason = str(exc)
        is_rate_limited = False
    except Exception as exc:
        fallback_reason = str(exc)
        is_rate_limited = False

    record = PRESET_FINANCIALS.get(symbol)
    if record is None:
        return None
    result = deepcopy(record)
    result["currency"] = "USD"
    result["exchange"] = "NASDAQ"
    result["sector"] = "Technology"
    status_label = "RATE_LIMITED" if is_rate_limited else "DEMO"
    result["provenance"] = {
        "source": status_label,
        "provenance": status_label,
        "source_type": status_label,
        "source_name": "ValuEngine Preset",
        "period": "LTM",
        "retrieved_date": str(date.today()),
        "currency": "USD",
        "notice": f"Alpha Vantage {status_label.lower().replace('_', ' ')}. {fallback_reason}",
    }
    result["_provenance"] = status_label
    return result


def json_safe(value: Any) -> Any:
    """Convert engine outputs (not their calculations) into JSON-safe values."""
    if isinstance(value, pd.DataFrame):
        return [{k: json_safe(v) for k, v in row.items()} for row in value.to_dict(orient="records")]
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, (np.integer, np.floating)):
        val = value.item()
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return val
    if isinstance(value, np.ndarray):
        return [json_safe(v) for v in value.tolist()]
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def envelope(result: dict[str, Any], financials: dict[str, Any] | None = None) -> dict[str, Any]:
    engine_status = result.get("status", "ERROR")
    status = engine_status if engine_status in {"VALID", "INVALID", "UNAVAILABLE"} else "ERROR"
    message = result.get("message")
    return {
        "status": status,
        "data": json_safe({key: value for key, value in result.items() if key not in {"status", "message"}}),
        "warnings": [],
        "errors": [message] if message and status in {"INVALID", "UNAVAILABLE", "ERROR"} else [],
        "provenance": financials.get("provenance", {}) if financials else {},
    }


def unavailable(ticker: str, mode: str = "local", message: str | None = None) -> dict[str, Any]:
    if message is None:
        if mode == "local":
            message = f"Ticker not available in Local Dataset ({ticker.upper()})"
        else:
            message = f"No live or demonstration data is available for {ticker.upper()}."
    return {
        "status": "UNAVAILABLE",
        "data": {},
        "warnings": [],
        "errors": [message],
        "provenance": {"source": "LOCAL_DB" if mode == "local" else "NONE", "notice": message},
    }


def search_companies(query: str, mode: str = "local", limit: int = 15) -> list[dict[str, Any]]:
    return _data_loader.store.search_companies(query, limit=limit)


def dcf(payload, mode: str | None = None) -> dict[str, Any]:
    m = mode or getattr(payload, "mode", "local")
    financials = company(payload.ticker, mode=m)
    if not financials:
        return unavailable(payload.ticker, mode=m)
    result = run_dcf(
        financials,
        payload.revenue_growth_rate,
        payload.ebitda_margin,
        payload.wacc,
        payload.terminal_growth_rate,
        payload.projection_years,
        payload.tax_rate,
        payload.mid_year_convention,
    )
    return envelope(result, financials)


def dcf_sensitivity(payload, mode: str | None = None) -> dict[str, Any]:
    m = mode or getattr(payload, "mode", "local")
    financials = company(payload.ticker, mode=m)
    if not financials:
        return unavailable(payload.ticker, mode=m)
    wacc_values = [payload.wacc - 0.01, payload.wacc - 0.005, payload.wacc, payload.wacc + 0.005, payload.wacc + 0.01]
    growth_values = [payload.terminal_growth_rate - 0.01, payload.terminal_growth_rate - 0.005, payload.terminal_growth_rate, payload.terminal_growth_rate + 0.005, payload.terminal_growth_rate + 0.01]
    wacc_terminal = []
    for growth in growth_values:
        row = []
        for wacc in wacc_values:
            result = run_dcf(financials, payload.revenue_growth_rate, payload.ebitda_margin, wacc, growth, payload.projection_years, payload.tax_rate, payload.mid_year_convention)
            row.append(result.get("implied_share_price") if result.get("status") == "VALID" else None)
        wacc_terminal.append(row)
    rev_values = [payload.revenue_growth_rate - 0.02, payload.revenue_growth_rate - 0.01, payload.revenue_growth_rate, payload.revenue_growth_rate + 0.01, payload.revenue_growth_rate + 0.02]
    margin_values = [payload.ebitda_margin - 0.04, payload.ebitda_margin - 0.02, payload.ebitda_margin, payload.ebitda_margin + 0.02, payload.ebitda_margin + 0.04]
    revenue_margin = []
    for margin in margin_values:
        row = []
        for growth in rev_values:
            result = run_dcf(financials, growth, margin, payload.wacc, payload.terminal_growth_rate, payload.projection_years, payload.tax_rate, payload.mid_year_convention)
            row.append(result.get("implied_share_price") if result.get("status") == "VALID" else None)
        revenue_margin.append(row)
    return {
        "status": "VALID",
        "data": {
            "wacc_values": wacc_values,
            "terminal_growth_values": growth_values,
            "wacc_terminal": json_safe(wacc_terminal),
            "revenue_growth_values": rev_values,
            "ebitda_margin_values": margin_values,
            "revenue_margin": json_safe(revenue_margin),
        },
        "warnings": [],
        "errors": [],
        "provenance": financials.get("provenance", {}),
    }


def mna(payload, mode: str | None = None) -> dict[str, Any]:
    m = mode or getattr(payload, "mode", "local")
    target, acquirer = company(payload.target_ticker, mode=m), company(payload.acquirer_ticker, mode=m)
    if not target:
        return unavailable(payload.target_ticker, mode=m)
    if not acquirer:
        return unavailable(payload.acquirer_ticker, mode=m)
    result = run_ma_model(
        acquirer,
        target,
        payload.offer_premium_pct,
        payload.pct_cash,
        payload.pct_stock,
        payload.debt_interest_rate,
        payload.revenue_synergies,
        payload.incremental_margin,
        payload.cost_synergies,
        payload.integration_costs,
        payload.tax_rate,
    )
    return envelope(result, target)


def lbo(payload, mode: str | None = None) -> dict[str, Any]:
    m = mode or getattr(payload, "mode", "local")
    financials = company(payload.ticker, mode=m)
    if not financials:
        return unavailable(payload.ticker, mode=m)
    result = run_lbo_model(
        financials,
        payload.entry_multiple,
        payload.senior_debt_pct,
        payload.sub_debt_pct,
        payload.senior_rate,
        payload.sub_rate,
        payload.exit_multiple,
        payload.revenue_growth,
        payload.ebitda_margin,
        payload.projection_years,
        payload.tax_rate,
    )
    return envelope(result, financials)


def trading_comps(ticker: str, mode: str = "local") -> dict[str, Any]:
    target = company(ticker, mode=mode)
    if not target:
        return unavailable(ticker, mode=mode)

    if mode == "local":
        target_sector = target.get("sector")
        peer_rows = _data_loader.store.get_peers(ticker, sector=target_sector, limit=12)
        if not peer_rows:
            return {
                "status": "UNAVAILABLE",
                "data": {},
                "warnings": ["Trading Comps unavailable: insufficient local peers in this sector."],
                "errors": ["No comparable peers found in local dataset."],
                "provenance": target.get("provenance", {}),
            }
        return envelope(run_trading_comps(target, peer_rows), target)

    # Live / Preset peers
    peers = [company(t, mode="live") for t in PRESET_FINANCIALS if t != ticker.upper()]
    return envelope(run_trading_comps(target, [p for p in peers if p]), target)


def transaction_comps(ticker: str, mode: str = "local") -> dict[str, Any]:
    target = company(ticker, mode=mode)
    if not target:
        return unavailable(ticker, mode=mode)
    return envelope(run_transaction_comps(target, []), target)


def analytics(payload, mode: str | None = None) -> dict[str, Any]:
    m = mode or getattr(payload, "mode", "local")
    financials = company(payload.ticker, mode=m)
    if not financials:
        return unavailable(payload.ticker, mode=m)
    result = r_risk_engine.run_monte_carlo(financials, payload)
    return envelope(result, financials)


def risk(payload, mode: str | None = None) -> dict[str, Any]:
    m = mode or getattr(payload, "mode", "local")
    financials = company(payload.ticker, mode=m)
    if not financials:
        return unavailable(payload.ticker, mode=m)
    result = run_stress_test(
        run_lbo_model,
        financials,
        10.0,
        0.4,
        0.2,
        0.08,
        0.10,
        11.0,
        payload.revenue_growth_rate,
        payload.ebitda_margin,
        payload.tax_rate,
    )
    return {
        "status": "VALID",
        "data": json_safe({"scenarios": result}),
        "warnings": [],
        "errors": [],
        "provenance": financials.get("provenance", {}),
    }


def risk_var(ticker: str, mode: str = "local") -> dict[str, Any]:
    financials = company(ticker, mode=mode)
    if not financials:
        return unavailable(ticker, mode=mode)
    result = r_risk_engine.run_var_cvar(financials)
    return envelope(result, financials)


def risk_merton(ticker: str, mode: str = "local") -> dict[str, Any]:
    financials = company(ticker, mode=mode)
    if not financials:
        return unavailable(ticker, mode=mode)
    result = r_risk_engine.run_merton(financials)
    return envelope(result, financials)


def risk_regime(ticker: str, mode: str = "local") -> dict[str, Any]:
    financials = company(ticker, mode=mode)
    if not financials:
        return unavailable(ticker, mode=mode)
    result = r_risk_engine.run_regime(financials)
    return envelope(result, financials)


def risk_factor_model(ticker: str, mode: str = "local") -> dict[str, Any]:
    financials = company(ticker, mode=mode)
    if not financials:
        return unavailable(ticker, mode=mode)
    result = r_risk_engine.run_factor_model(financials)
    return envelope(result, financials)


def risk_evt(ticker: str, mode: str = "local") -> dict[str, Any]:
    financials = company(ticker, mode=mode)
    if not financials:
        return unavailable(ticker, mode=mode)
    result = r_risk_engine.run_tail_risk(financials)
    return envelope(result, financials)


def risk_copula(acquirer_ticker: str, target_ticker: str, mode: str = "local") -> dict[str, Any]:
    acq = company(acquirer_ticker, mode=mode)
    tgt = company(target_ticker, mode=mode)
    if not acq:
        return unavailable(acquirer_ticker, mode=mode)
    if not tgt:
        return unavailable(target_ticker, mode=mode)
    result = r_risk_engine.run_copula(acq, tgt)
    return envelope(result, acq)


def valuation_confidence(ticker: str, mode: str = "local") -> dict[str, Any]:
    financials = company(ticker, mode=mode)
    if not financials:
        return unavailable(ticker, mode=mode)
    result = r_risk_engine.calculate_confidence(financials)
    return envelope(result, financials)


def health(ticker: str, acquirer_ticker: str = "MSFT", mode: str = "local") -> dict[str, Any]:
    target, acquirer = company(ticker, mode=mode), company(acquirer_ticker, mode=mode)
    if not target:
        return unavailable(ticker, mode=mode)
    if not acquirer:
        return unavailable(acquirer_ticker, mode=mode)
    dcf_result = run_dcf(target, 0.07, 0.25, 0.085, 0.025, 5, 0.21, False)
    ma_result = run_ma_model(acquirer, target, 0.25, 0.5, 0.5, 0.08, 0, 0.20, 0, 0, 0.21)
    lbo_result = run_lbo_model(target, 10.0, 0.4, 0.2, 0.08, 0.10, 11.0, 0.07, 0.25, 5, 0.21)
    issues = run_data_quality_checks(target)
    model = evaluate_model_health(dcf_result, ma_result, lbo_result, issues)
    quality = calculate_deal_quality(dcf_result, ma_result, lbo_result, {})
    health_status = (
        model["status"]
        .replace("🟢 ", "")
        .replace("🟡 ", "")
        .replace("🔴 ", "")
        .replace("ðŸŸ¢ ", "")
        .replace("ðŸŸ¡ ", "")
        .replace("ðŸ”´ ", "")
        .strip()
    )
    normalized = "VALID" if health_status == "VALID" else "REVIEW_REQUIRED" if "REVIEW" in health_status else "INVALID"
    return {
        "status": normalized,
        "data": {
            "status_label": health_status,
            "flags": model["flags"],
            "deal_quality": quality,
        },
        "warnings": [],
        "errors": [],
        "provenance": target.get("provenance", {}),
    }


def data_quality(ticker: str, mode: str = "local") -> dict[str, Any]:
    target = company(ticker, mode=mode)
    if not target:
        return unavailable(ticker, mode=mode)
    issues = run_data_quality_checks(target)
    return {
        "status": "VALID",
        "data": {"issues": issues, "check_count": len(issues)},
        "warnings": [issue["message"] for issue in issues if issue["severity"] == "WARNING"],
        "errors": [],
        "provenance": target.get("provenance", {}),
    }


def export_excel(target_ticker: str, acquirer_ticker: str, mode: str = "local") -> Path | None:
    target, acquirer = company(target_ticker, mode=mode), company(acquirer_ticker, mode=mode)
    if not target or not acquirer:
        return None
    dcf_result = run_dcf(target, 0.07, 0.25, 0.085, 0.025)
    ma_result = run_ma_model(acquirer, target, 0.25, 0.5, 0.5, 0.08, 0, 0.20, 0, 0, 0.21)
    lbo_result = run_lbo_model(target, 10.0, 0.4, 0.2, 0.08, 0.10, 11.0, 0.07, 0.25)
    handle = NamedTemporaryFile(delete=False, suffix=".xlsx", prefix="valuengine_")
    handle.close()
    ExcelReportExporter().export_full_model(dcf_result, ma_result, lbo_result, handle.name)
    return Path(handle.name)
