import json
import random
from typing import Dict, Any, List

from .r_integration import call_r_script, is_r_available
from .dcf_engine import run_dcf


def _extract_returns(financials: Dict[str, Any], default_len: int = 100) -> list[float]:
    """Extract percentage returns from historical prices if present; fallback to deterministic randoms."""
    prices = financials.get("historical_prices")
    if isinstance(prices, list) and len(prices) >= 2:
        sorted_prices = sorted(prices, key=lambda p: str(p.get("date", "")))
        closes = [float(p["close"]) for p in sorted_prices if p.get("close") is not None]
        returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes)) if closes[i - 1] > 0]
        if len(returns) >= 10:
            return returns
    random.seed(42)
    return [random.gauss(0.001, 0.02) for _ in range(default_len)]


def run_monte_carlo(financials: Dict[str, Any], payload: Any) -> Dict[str, Any]:
    # Call R to get generated scenarios
    input_data = {
        "iterations": payload.iterations,
        "base_rev_growth": payload.revenue_growth_rate,
        "base_ebitda_margin": payload.ebitda_margin,
        "base_wacc": payload.wacc,
        "base_term_growth": payload.terminal_growth_rate,
    }
    scenarios = call_r_script("monte_carlo.R", input_data)
    
    if scenarios.get("status") == "UNAVAILABLE":
        return scenarios

    # Run Python DCF for each scenario
    prices = []
    revs = scenarios.get("rev_samples", [])
    margins = scenarios.get("margin_samples", [])
    waccs = scenarios.get("wacc_samples", [])
    terms = scenarios.get("term_samples", [])
    
    iterations = min(len(revs), len(margins), len(waccs), len(terms), payload.iterations)
    
    for i in range(iterations):
        res = run_dcf(
            financials=financials,
            revenue_growth_rate=revs[i],
            ebitda_margin=margins[i],
            wacc=waccs[i],
            terminal_growth_rate=terms[i],
            projection_years=payload.projection_years,
            tax_rate=payload.tax_rate,
            mid_year_convention=payload.mid_year_convention,
        )
        if res.get("status") == "VALID":
            prices.append(res.get("implied_share_price", 0.0))

    if not prices:
        return {"status": "UNAVAILABLE", "message": "Failed to calculate valid DCF valuations from scenarios."}

    # Call R to calculate risk metrics
    metrics_input = {
        "valuations": prices,
        "threshold": prices[0] if prices else 0.0,  # base valuation roughly
    }
    metrics = call_r_script("risk_metrics.R", metrics_input)
    if metrics.get("status") == "UNAVAILABLE":
        return metrics

    # Call R for assumption impact
    impact_input = {
        "samples": {
            "rev": revs[:len(prices)],
            "margin": margins[:len(prices)],
            "wacc": waccs[:len(prices)],
            "term": terms[:len(prices)],
        },
        "valuations": prices,
    }
    impact = call_r_script("assumption_impact.R", impact_input)
    
    return {
        "status": "VALID",
        "simulation_count": iterations,
        "metrics": metrics,
        "impact_analysis": impact.get("impacts", []),
        "methodology": {
            "sampling": scenarios.get("methodology"),
            "impact": impact.get("methodology"),
        },
        "distribution": prices,
    }


def run_var_cvar(financials: Dict[str, Any]) -> Dict[str, Any]:
    returns = _extract_returns(financials, default_len=100)
    input_data = {
        "returns": returns,
        "confidence": 0.95,
        "horizon": 1,
    }
    return call_r_script("var_cvar.R", input_data)


def run_merton(financials: Dict[str, Any]) -> Dict[str, Any]:
    eq_val = financials.get("market_cap", 0)
    debt = financials.get("total_debt", 0)
    
    if not eq_val or not debt:
        return {"status": "UNAVAILABLE", "message": "Missing market cap or debt for Merton model"}
        
    input_data = {
        "equity_value": float(eq_val),
        "debt": float(debt),
        "equity_volatility": 0.3,
        "risk_free_rate": 0.04,
        "debt_maturity": 5.0,
    }
    return call_r_script("merton.R", input_data)


def run_regime(financials: Dict[str, Any]) -> Dict[str, Any]:
    returns = _extract_returns(financials, default_len=100)
    input_data = {"returns": returns}
    return call_r_script("regime.R", input_data)


def run_factor_model(financials: Dict[str, Any]) -> Dict[str, Any]:
    mock_len = 100
    returns = _extract_returns(financials, default_len=mock_len)
    random.seed(42)
    input_data = {
        "returns": returns,
        "mkt": [random.gauss(0, 0.015) for _ in range(len(returns))],
        "smb": [random.gauss(0, 0.005) for _ in range(len(returns))],
        "hml": [random.gauss(0, 0.005) for _ in range(len(returns))],
        "rmw": [random.gauss(0, 0.005) for _ in range(len(returns))],
        "cma": [random.gauss(0, 0.005) for _ in range(len(returns))],
    }
    return call_r_script("factor_model.R", input_data)


def run_tail_risk(financials: Dict[str, Any]) -> Dict[str, Any]:
    returns = _extract_returns(financials, default_len=200)
    input_data = {"returns": returns}
    return call_r_script("tail_risk.R", input_data)


def run_copula(acquirer: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
    acq_returns = _extract_returns(acquirer, default_len=100)
    tgt_returns = _extract_returns(target, default_len=100)
    input_data = {
        "acquirer_returns": acq_returns,
        "target_returns": tgt_returns,
    }
    return call_r_script("copula.R", input_data)


def calculate_confidence(financials: Dict[str, Any]) -> Dict[str, Any]:
    # Valuation Confidence Engine
    issues = financials.get("data_quality_issues", [])
    data_score = max(0, 100 - len(issues) * 10)
    
    mc_status = is_r_available()
    model_score = 90 if mc_status else 50
    
    final_score = (data_score + model_score) / 2
    
    return {
        "status": "VALID",
        "score": final_score,
        "components": {
            "data_quality_score": data_score,
            "model_availability_score": model_score,
        },
    }
