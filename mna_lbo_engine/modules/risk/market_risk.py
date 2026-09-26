"""Market risk: Value-at-Risk and Expected Shortfall (historical, normal, Cornish-Fisher) and
extreme value theory (peaks-over-threshold with a Generalized Pareto tail).

Losses are expressed as positive fractions of position value over one trading day; 10-day
figures use square-root-of-time scaling (an approximation that ignores volatility clustering).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import stats

from .returns import InsufficientData, max_drawdown, simple_returns

CONFIDENCE_LEVELS = (0.95, 0.99)


def _cornish_fisher_z(z: np.ndarray | float, skew: float, excess_kurt: float) -> np.ndarray | float:
    return (z + (z ** 2 - 1) * skew / 6 + (z ** 3 - 3 * z) * excess_kurt / 24
            - (2 * z ** 3 - 5 * z) * skew ** 2 / 36)


def value_at_risk(prices: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        r = simple_returns(prices, minimum=100).to_numpy()
    except InsufficientData as exc:
        return {"status": "UNAVAILABLE", "message": str(exc)}
    mu, sigma = float(r.mean()), float(r.std(ddof=1))
    skew = float(stats.skew(r, bias=False))
    excess_kurt = float(stats.kurtosis(r, fisher=True, bias=False))
    jb_stat, jb_p = stats.jarque_bera(r)

    table = []
    for confidence in CONFIDENCE_LEVELS:
        alpha = 1 - confidence
        q = float(np.quantile(r, alpha))
        hist_var, hist_es = -q, -float(r[r <= q].mean())
        z = stats.norm.ppf(alpha)
        normal_var = -(mu + sigma * z)
        normal_es = -(mu - sigma * stats.norm.pdf(z) / alpha)
        cf_var = -(mu + sigma * _cornish_fisher_z(z, skew, excess_kurt))
        tail_levels = np.linspace(alpha / 200, alpha, 200)
        cf_es = float(np.mean(-(mu + sigma * _cornish_fisher_z(stats.norm.ppf(tail_levels), skew, excess_kurt))))
        for method, var, es in (("historical", hist_var, hist_es), ("normal", normal_var, normal_es),
                                ("cornish_fisher", cf_var, cf_es)):
            table.append({
                "method": method, "confidence": confidence, "var_1d": var, "es_1d": es,
                "var_10d": var * math.sqrt(10), "es_10d": es * math.sqrt(10),
            })

    counts, edges = np.histogram(r, bins=40)
    centers = (edges[:-1] + edges[1:]) / 2
    width = edges[1] - edges[0]
    normal_density = stats.norm.pdf(centers, mu, sigma) * len(r) * width
    return {
        "status": "VALID",
        "observations": int(len(r)),
        "mean_daily_return": mu,
        "daily_volatility": sigma,
        "annualized_volatility": sigma * math.sqrt(252),
        "skewness": skew,
        "excess_kurtosis": excess_kurt,
        "jarque_bera_p_value": float(jb_p),
        "normality_rejected": bool(jb_p < 0.05),
        "worst_day": float(r.min()),
        "best_day": float(r.max()),
        "table": table,
        "histogram": [{"value": float(c), "count": int(n), "normal": float(d)}
                      for c, n, d in zip(centers, counts, normal_density)],
        **max_drawdown(prices),
        "methodology": "Historical simulation, Gaussian parametric and Cornish-Fisher (skew/kurtosis-adjusted) "
                       "VaR/ES on daily simple returns; 10-day figures scaled by sqrt(10).",
    }


def tail_risk_evt(prices: list[dict[str, Any]], threshold_quantile: float = 0.90) -> dict[str, Any]:
    try:
        r = simple_returns(prices, minimum=150).to_numpy()
    except InsufficientData as exc:
        return {"status": "UNAVAILABLE", "message": str(exc)}
    losses = -r
    u = float(np.quantile(losses, threshold_quantile))
    excess = losses[losses > u] - u
    n, n_u = len(losses), len(excess)
    if n_u < 10:
        return {"status": "UNAVAILABLE", "message": f"Only {n_u} exceedances above the threshold; GPD fit not possible."}
    try:
        xi, _, beta = stats.genpareto.fit(excess, floc=0)
    except Exception as exc:  # scipy optimiser failure
        return {"status": "UNAVAILABLE", "message": f"GPD fit failed: {exc}"}
    if beta <= 0 or not np.isfinite(xi):
        return {"status": "UNAVAILABLE", "message": "GPD fit returned invalid parameters."}

    def pot_var(q: float) -> float:
        base = (n / n_u) * (1 - q)
        return u + (beta / xi) * (base ** (-xi) - 1) if abs(xi) > 1e-6 else u - beta * math.log(base)

    def pot_es(var: float) -> float | None:
        return (var + beta - xi * u) / (1 - xi) if xi < 1 else None

    levels = []
    for q in (0.99, 0.995, 0.999):
        var = pot_var(q)
        levels.append({"confidence": q, "var_1d": var, "es_1d": pot_es(var),
                       "empirical_var_1d": float(np.quantile(losses, q)) if q <= 1 - 1 / n else None})
    ks_stat, ks_p = stats.kstest(excess, "genpareto", args=(xi, 0, beta))
    tail = ("heavy (power-law) tail" if xi > 0.05 else "light, bounded tail" if xi < -0.05 else "exponential-type tail")
    sorted_excess = np.sort(excess)
    empirical_p = (np.arange(1, n_u + 1) - 0.5) / n_u
    return {
        "status": "VALID",
        "threshold": u,
        "threshold_quantile": threshold_quantile,
        "exceedances": n_u,
        "observations": n,
        "shape_xi": float(xi),
        "scale_beta": float(beta),
        "tail_interpretation": tail,
        "levels": levels,
        "ks_p_value": float(ks_p),
        "qq": [{"empirical": float(e), "model": float(stats.genpareto.ppf(p, xi, 0, beta))}
               for e, p in zip(sorted_excess, empirical_p)],
        "low_sample_warning": n_u < 25,
        "methodology": f"Peaks-over-threshold: losses above the {threshold_quantile:.0%} quantile fitted to a Generalized "
                       "Pareto distribution by maximum likelihood; tail VaR/ES from the POT formulas.",
    }
