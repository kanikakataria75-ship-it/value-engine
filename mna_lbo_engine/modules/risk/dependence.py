"""Joint tail dependence between two stocks via copulas.

Returns are aligned by trading date, converted to pseudo-observations (ranks / (n + 1)) and
four one-parameter-family copulas are fitted by maximum likelihood:
  Gaussian (no tail dependence), Student-t (symmetric tails), Clayton (lower tail), Gumbel (upper tail).
The model with the lowest AIC is selected. Joint-crash probability is P(both returns fall below their
own 5% quantile) from the fitted copula, compared with the empirical frequency and independence.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import optimize, special, stats

from .returns import InsufficientData, aligned_log_returns

CRASH_QUANTILE = 0.05


def _ll_gaussian(rho: float, z1: np.ndarray, z2: np.ndarray) -> float:
    r2 = rho * rho
    return float(np.sum(-0.5 * math.log(1 - r2) - (r2 * (z1 ** 2 + z2 ** 2) - 2 * rho * z1 * z2) / (2 * (1 - r2))))


def _ll_student(rho: float, nu: float, u: np.ndarray, v: np.ndarray) -> float:
    t1, t2 = stats.t.ppf(u, nu), stats.t.ppf(v, nu)
    r2 = rho * rho
    log_f2 = (special.gammaln((nu + 2) / 2) - special.gammaln(nu / 2) - math.log(nu * math.pi) - 0.5 * math.log(1 - r2)
              - (nu + 2) / 2 * np.log1p((t1 ** 2 - 2 * rho * t1 * t2 + t2 ** 2) / (nu * (1 - r2))))
    return float(np.sum(log_f2 - stats.t.logpdf(t1, nu) - stats.t.logpdf(t2, nu)))


def _ll_clayton(theta: float, u: np.ndarray, v: np.ndarray) -> float:
    s = u ** (-theta) + v ** (-theta) - 1
    return float(np.sum(math.log1p(theta) + (-1 - theta) * (np.log(u) + np.log(v)) + (-2 - 1 / theta) * np.log(s)))


def _ll_gumbel(theta: float, u: np.ndarray, v: np.ndarray) -> float:
    lu, lv = -np.log(u), -np.log(v)
    a = lu ** theta + lv ** theta
    a_inv = a ** (1 / theta)
    return float(np.sum(-a_inv + lu + lv + (theta - 1) * (np.log(lu) + np.log(lv)) - (2 - 1 / theta) * np.log(a)
                        + np.log(a_inv + theta - 1)))


def _joint_lower(family: str, params: dict[str, float], q: float) -> float:
    if family == "gaussian":
        z = stats.norm.ppf(q)
        rho = params["rho"]
        return float(stats.multivariate_normal(mean=[0, 0], cov=[[1, rho], [rho, 1]]).cdf([z, z]))
    if family == "student_t":
        nu, rho = params["nu"], params["rho"]
        t = stats.t.ppf(q, nu)
        return float(stats.multivariate_t(loc=[0, 0], shape=[[1, rho], [rho, 1]], df=nu).cdf([t, t]))
    if family == "clayton":
        theta = params["theta"]
        return float((2 * q ** (-theta) - 1) ** (-1 / theta))
    theta = params["theta"]  # gumbel: C(q, q) = q^(2^(1/theta))
    return float(q ** (2 ** (1 / theta)))


def copula_analysis(prices_a: list[dict[str, Any]], prices_b: list[dict[str, Any]],
                    label_a: str, label_b: str) -> dict[str, Any]:
    try:
        frame = aligned_log_returns(prices_a, prices_b, minimum=100)
    except InsufficientData as exc:
        return {"status": "UNAVAILABLE", "message": str(exc)}
    x, y = frame["a"].to_numpy(), frame["b"].to_numpy()
    n = len(x)
    u = stats.rankdata(x) / (n + 1)
    v = stats.rankdata(y) / (n + 1)
    tau = float(stats.kendalltau(x, y).statistic)
    spearman = float(stats.spearmanr(x, y).statistic)
    pearson = float(np.corrcoef(x, y)[0, 1])

    fits: list[dict[str, Any]] = []
    z1, z2 = stats.norm.ppf(u), stats.norm.ppf(v)
    rho_g = float(optimize.minimize_scalar(lambda r: -_ll_gaussian(r, z1, z2), bounds=(-0.99, 0.99), method="bounded").x)
    ll = _ll_gaussian(rho_g, z1, z2)
    fits.append({"family": "gaussian", "params": {"rho": rho_g}, "log_likelihood": ll, "aic": 2 - 2 * ll,
                 "lower_tail": 0.0, "upper_tail": 0.0})

    rho_t = float(np.clip(math.sin(math.pi * tau / 2), -0.99, 0.99))
    nu_fit = optimize.minimize_scalar(lambda nu: -_ll_student(rho_t, nu, u, v), bounds=(2.05, 60.0), method="bounded")
    nu = float(nu_fit.x)
    ll = _ll_student(rho_t, nu, u, v)
    lam = float(2 * stats.t.cdf(-math.sqrt((nu + 1) * (1 - rho_t) / (1 + rho_t)), nu + 1))
    fits.append({"family": "student_t", "params": {"rho": rho_t, "nu": nu}, "log_likelihood": ll, "aic": 4 - 2 * ll,
                 "lower_tail": lam, "upper_tail": lam})

    if tau > 0.02:
        theta_c = float(optimize.minimize_scalar(lambda t: -_ll_clayton(t, u, v), bounds=(1e-3, 20.0), method="bounded").x)
        ll = _ll_clayton(theta_c, u, v)
        fits.append({"family": "clayton", "params": {"theta": theta_c}, "log_likelihood": ll, "aic": 2 - 2 * ll,
                     "lower_tail": float(2 ** (-1 / theta_c)), "upper_tail": 0.0})
        theta_g = float(optimize.minimize_scalar(lambda t: -_ll_gumbel(t, u, v), bounds=(1.0001, 20.0), method="bounded").x)
        ll = _ll_gumbel(theta_g, u, v)
        fits.append({"family": "gumbel", "params": {"theta": theta_g}, "log_likelihood": ll, "aic": 2 - 2 * ll,
                     "lower_tail": 0.0, "upper_tail": float(2 - 2 ** (1 / theta_g))})

    best = min(fits, key=lambda f: f["aic"])
    q = CRASH_QUANTILE
    model_joint = _joint_lower(best["family"], best["params"], q)
    empirical_joint = float(np.mean((u <= q) & (v <= q)))

    def empirical_tail(level: float) -> dict[str, float]:
        return {"quantile": level,
                "lower": float(np.mean((u <= level) & (v <= level)) / level),
                "upper": float(np.mean((u > 1 - level) & (v > 1 - level)) / level)}

    rolling = frame["a"].rolling(60).corr(frame["b"]).dropna()
    rng = np.random.default_rng(3)
    idx = np.sort(rng.choice(n, size=min(n, 300), replace=False))
    names = {"gaussian": "Gaussian", "student_t": "Student-t", "clayton": "Clayton", "gumbel": "Gumbel"}
    return {
        "status": "VALID",
        "pair": {"a": label_a, "b": label_b},
        "observations": n,
        "start_date": str(frame.index[0].date()),
        "end_date": str(frame.index[-1].date()),
        "kendall_tau": tau,
        "spearman_rho": spearman,
        "pearson_correlation": pearson,
        "selected_copula": names[best["family"]],
        "selected_family": best["family"],
        "selected_params": best["params"],
        "lower_tail_dependence": best["lower_tail"],
        "upper_tail_dependence": best["upper_tail"],
        "fits": [{**f, "name": names[f["family"]]} for f in sorted(fits, key=lambda f: f["aic"])],
        "joint_crash": {
            "quantile": q,
            "model_probability": model_joint,
            "empirical_probability": empirical_joint,
            "independence_probability": q * q,
            "multiple_of_independence": model_joint / (q * q),
        },
        "empirical_tail_dependence": [empirical_tail(0.05), empirical_tail(0.10)],
        "rolling_correlation": [{"date": str(d.date()), "correlation": float(c)} for d, c in rolling.items()],
        "pseudo_observations": [{"u": float(u[i]), "v": float(v[i])} for i in idx],
        "methodology": "Returns aligned on common trading dates; Gaussian, Student-t, Clayton and Gumbel copulas fitted "
                       "by maximum likelihood on pseudo-observations and ranked by AIC.",
    }
