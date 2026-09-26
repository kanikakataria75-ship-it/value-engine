"""Merton structural credit model.

Equity is a European call on firm assets V with strike equal to the default point D:
    E        = V N(d1) - D e^{-rT} N(d2)
    sigma_E E = N(d1) sigma_V V
Both equations are solved jointly for the unobserved (V, sigma_V) with a Newton-type root finder.
Equity volatility is realised volatility from daily log returns; the default point is total debt
(the dataset has no short/long-term split); the horizon is one year. The resulting default
probability is risk-neutral, which overstates real-world default rates.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import optimize, stats

from ...config import market_parameters
from ..common import is_balance_sheet_financial, num
from .returns import InsufficientData, log_returns


def solve_merton(equity: float, debt: float, sigma_e: float, r: float, horizon: float = 1.0) -> dict[str, Any] | None:
    sqrt_t = math.sqrt(horizon)

    def residuals(x: np.ndarray) -> list[float]:
        v, s = math.exp(x[0]), math.exp(x[1])
        d1 = (math.log(v / debt) + (r + 0.5 * s * s) * horizon) / (s * sqrt_t)
        d2 = d1 - s * sqrt_t
        eq_model = v * stats.norm.cdf(d1) - debt * math.exp(-r * horizon) * stats.norm.cdf(d2)
        return [eq_model / equity - 1.0, stats.norm.cdf(d1) * s * v / (sigma_e * equity) - 1.0]

    start = [math.log(equity + debt * math.exp(-r * horizon)), math.log(max(sigma_e * equity / (equity + debt), 1e-4))]
    solution = optimize.root(residuals, start, method="hybr", tol=1e-12)
    if not solution.success or max(abs(v) for v in residuals(solution.x)) > 1e-8:
        return None
    v, s = math.exp(solution.x[0]), math.exp(solution.x[1])
    d1 = (math.log(v / debt) + (r + 0.5 * s * s) * horizon) / (s * sqrt_t)
    d2 = d1 - s * sqrt_t
    debt_value = v - equity
    risk_free_debt = debt * math.exp(-r * horizon)
    spread = -math.log(debt_value / risk_free_debt) / horizon if debt_value > 0 else None
    return {
        "asset_value": v, "asset_volatility": s, "d1": d1, "distance_to_default": d2,
        "probability_of_default": float(stats.norm.cdf(-d2)), "market_leverage": debt / v,
        "implied_credit_spread": spread, "max_residual": max(abs(x) for x in residuals(solution.x)),
    }


def merton_analysis(company: dict[str, Any], prices: list[dict[str, Any]], horizon: float = 1.0) -> dict[str, Any]:
    equity = num(company, "market_cap")
    debt = num(company, "total_debt")
    if not equity or equity <= 0:
        return {"status": "UNAVAILABLE", "message": "Market capitalisation is missing."}
    if debt is None:
        return {"status": "UNAVAILABLE", "message": "Total debt is not reported."}
    try:
        returns = log_returns(prices, minimum=120)
    except InsufficientData as exc:
        return {"status": "UNAVAILABLE", "message": str(exc)}
    sigma_e = float(returns.std(ddof=1) * math.sqrt(252))
    r = market_parameters(company.get("currency")).risk_free_rate
    base = {
        "inputs": {"equity_value": equity, "default_point": debt, "equity_volatility": sigma_e,
                   "risk_free_rate": r, "horizon_years": horizon, "volatility_window_days": int(len(returns))},
        "methodology": "Merton (1974): joint solve of the equity-value and volatility equations; realised 1Y equity "
                       "volatility; default point = total debt; 1-year horizon; risk-neutral PD.",
    }
    if debt <= 0:
        return {"status": "VALID", **base, "asset_value": equity, "asset_volatility": sigma_e, "distance_to_default": None,
                "probability_of_default": 0.0, "market_leverage": 0.0, "implied_credit_spread": 0.0,
                "note": "No financial debt: default risk in the Merton sense is nil.", "sensitivity": []}
    solved = solve_merton(equity, debt, sigma_e, r, horizon)
    if solved is None:
        return {"status": "UNAVAILABLE", "message": "The Merton equations did not converge for these inputs.", **base}
    sensitivity = []
    for multiplier in (0.8, 1.0, 1.2, 1.5):
        alt = solve_merton(equity, debt, sigma_e * multiplier, r, horizon)
        if alt:
            sensitivity.append({"equity_volatility": sigma_e * multiplier,
                                "distance_to_default": alt["distance_to_default"],
                                "probability_of_default": alt["probability_of_default"]})
    status, note = "VALID", None
    if is_balance_sheet_financial(company):
        status = "REVIEW_REQUIRED"
        note = "For banks, insurers and lenders, total debt includes operating funding; the Merton PD is not a meaningful credit measure."
    return {"status": status, **base, **solved, "sensitivity": sensitivity, "note": note}
