"""Monte Carlo valuation, variance attribution and tornado sensitivity on the DCF.

Uncertain inputs: revenue growth, target EBITDA margin, WACC and terminal growth. They are drawn
jointly from a multivariate normal with
  * growth / margin volatility calibrated to the company's own history (bounded), with defaults
    when fewer than three years of history exist;
  * correlation +0.3 between growth and margin (operating leverage) and +0.5 between WACC and
    terminal growth (both move with interest rates).
Draws that would put terminal growth within 1% of WACC are pulled back to WACC - 1%.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from ..common import clamp
from ..dcf_engine import DcfInputError, DcfInputs, build_context, project, validate_inputs

CORRELATION = np.array([
    [1.0, 0.3, 0.0, 0.0],
    [0.3, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.5],
    [0.0, 0.0, 0.5, 1.0],
])
LABELS = ["Revenue growth", "EBITDA margin", "WACC", "Terminal growth"]
KEYS = ["revenue_growth", "ebitda_margin", "wacc", "terminal_growth"]


def calibrate_volatility(history: dict[str, Any] | None) -> dict[str, float]:
    growth_vol = (history or {}).get("growth_volatility")
    margin_vol = (history or {}).get("margin_volatility")
    return {
        "revenue_growth": clamp(growth_vol, 0.01, 0.10) if growth_vol is not None else 0.03,
        "ebitda_margin": clamp(margin_vol, 0.005, 0.06) if margin_vol is not None else 0.02,
        "wacc": 0.0075,
        "terminal_growth": 0.005,
    }


def draw_scenarios(inputs: DcfInputs, vols: dict[str, float], iterations: int, seed: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    z = rng.multivariate_normal(np.zeros(4), CORRELATION, size=iterations)
    base = np.array([getattr(inputs, k) for k in KEYS])
    sigma = np.array([vols[k] for k in KEYS])
    draws = base + z * sigma
    g = np.clip(draws[:, 0], -0.3, 0.6)
    m = np.clip(draws[:, 1], -0.5, 0.95)
    w = np.clip(draws[:, 2], 0.02, 0.4)
    tg = np.clip(draws[:, 3], -0.02, 0.08)
    adjusted = tg > w - 0.01
    tg = np.where(adjusted, w - 0.01, tg)
    return {"revenue_growth": g, "ebitda_margin": m, "wacc": w, "terminal_growth": tg, "adjusted": adjusted}


def run_monte_carlo(company: dict[str, Any], inputs: DcfInputs, history: dict[str, Any] | None,
                    iterations: int = 5000, seed: int = 2024) -> dict[str, Any]:
    error = validate_inputs(inputs)
    if error:
        return {"status": "INVALID", "message": error}
    try:
        ctx = build_context(company, inputs.tax_rate)
    except DcfInputError as exc:
        return {"status": "INVALID", "message": str(exc)}
    ronic = max(inputs.ronic or max(inputs.wacc, ctx.roic or inputs.wacc), inputs.terminal_growth + 0.01)
    resolved = replace(inputs, ronic=ronic)
    vols = calibrate_volatility(history)
    draws = draw_scenarios(resolved, vols, iterations, seed)
    out = project(ctx, resolved, draws["revenue_growth"], draws["ebitda_margin"], draws["wacc"], draws["terminal_growth"])
    prices = out["price"]
    valid = np.isfinite(prices)
    prices = prices[valid]
    if prices.size < iterations * 0.5:
        return {"status": "INVALID", "message": "Too many scenarios produced undefined values."}

    market = ctx.current_price
    pct = lambda q: float(np.percentile(prices, q))  # noqa: E731
    counts, edges = np.histogram(prices, bins=40)
    x = np.column_stack([draws[k][valid] for k in KEYS])
    x_std = (x - x.mean(axis=0)) / x.std(axis=0)
    y_std = (prices - prices.mean()) / prices.std()
    coefs, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(y_std)), x_std]), y_std, rcond=None)
    std_coefs = coefs[1:]
    shares = std_coefs ** 2 / np.sum(std_coefs ** 2)
    fitted = np.column_stack([np.ones(len(y_std)), x_std]) @ coefs
    r_squared = 1 - np.sum((y_std - fitted) ** 2) / np.sum(y_std ** 2)

    base_price = float(project(ctx, resolved)["price"][0])
    arg_names = {"revenue_growth": "growth", "ebitda_margin": "margin", "wacc": "wacc", "terminal_growth": "terminal_growth"}
    tornado = []
    for key, label in zip(KEYS, LABELS):
        low_value = getattr(resolved, key) - 1.2816 * vols[key]
        high_value = getattr(resolved, key) + 1.2816 * vols[key]
        if key == "terminal_growth":
            high_value = min(high_value, resolved.wacc - 0.01)
        if key == "wacc":
            low_value = max(low_value, resolved.terminal_growth + 0.01)
        price_low, price_high = (float(project(ctx, resolved, **{arg_names[key]: value})["price"][0])
                                 for value in (low_value, high_value))
        tornado.append({"variable": key, "label": label, "low_input": low_value, "high_input": high_value,
                        "price_at_low": price_low, "price_at_high": price_high, "swing": abs(price_high - price_low)})
    tornado.sort(key=lambda t: t["swing"], reverse=True)

    sample_idx = np.random.default_rng(seed + 1).choice(prices.size, size=min(600, prices.size), replace=False)
    return {
        "status": "VALID",
        "currency": ctx.currency,
        "iterations": iterations,
        "valid_scenarios": int(prices.size),
        "seed": seed,
        "adjusted_terminal_growth_draws": int(draws["adjusted"].sum()),
        "base_price": base_price,
        "current_price": market,
        "metrics": {
            "mean": float(prices.mean()), "median": pct(50), "std": float(prices.std(ddof=1)),
            "p05": pct(5), "p10": pct(10), "p25": pct(25), "p75": pct(75), "p90": pct(90), "p95": pct(95),
            "prob_below_market": float(np.mean(prices < market)) if market else None,
            "prob_above_market": float(np.mean(prices > market)) if market else None,
            "prob_negative": float(np.mean(prices < 0)),
        },
        "histogram": [{"start": float(a), "end": float(b), "mid": float((a + b) / 2), "count": int(c)}
                      for a, b, c in zip(edges[:-1], edges[1:], counts)],
        "input_volatility": vols,
        "correlation": CORRELATION.tolist(),
        "attribution": [
            {"variable": key, "label": label, "standardized_coefficient": float(c), "variance_share": float(s)}
            for key, label, c, s in sorted(zip(KEYS, LABELS, std_coefs, shares), key=lambda t: -t[3])
        ],
        "attribution_r_squared": float(r_squared),
        "tornado": tornado,
        "sample": [{"revenue_growth": float(draws["revenue_growth"][valid][i]), "ebitda_margin": float(draws["ebitda_margin"][valid][i]),
                    "price": float(prices[i])} for i in sample_idx],
        "methodology": "Correlated normal draws of growth, margin, WACC and terminal growth (volatilities from the "
                       "company's history), each valued with the vectorised DCF. Variance shares are normalised squared "
                       "standardised regression coefficients (approximate because inputs are correlated). Tornado swings "
                       "move one input to its 10th / 90th percentile with the others at base.",
    }
