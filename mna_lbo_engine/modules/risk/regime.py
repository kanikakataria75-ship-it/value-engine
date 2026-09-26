"""Volatility regimes from a two-state Gaussian hidden Markov model.

Daily log returns are modelled as draws from one of two normal distributions (a calm and a
turbulent state) with Markov switching between them. Parameters are estimated by expectation-
maximisation (Baum-Welch) with scaled forward-backward recursions and several random starts.
A BIC comparison against a single normal distribution reports whether regimes are supported.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from .returns import InsufficientData, log_returns


def _normal_pdf(x: np.ndarray, mu: np.ndarray, var: np.ndarray) -> np.ndarray:
    return np.exp(-0.5 * (x[:, None] - mu[None, :]) ** 2 / var[None, :]) / np.sqrt(2 * np.pi * var[None, :])


def _forward_backward(x: np.ndarray, pi: np.ndarray, A: np.ndarray, mu: np.ndarray, var: np.ndarray):
    T, k = len(x), len(pi)
    B = np.maximum(_normal_pdf(x, mu, var), 1e-300)
    alpha = np.zeros((T, k))
    scale = np.zeros(T)
    alpha[0] = pi * B[0]
    scale[0] = alpha[0].sum()
    alpha[0] /= scale[0]
    for t in range(1, T):
        alpha[t] = (alpha[t - 1] @ A) * B[t]
        scale[t] = alpha[t].sum()
        alpha[t] /= scale[t]
    beta = np.ones((T, k))
    for t in range(T - 2, -1, -1):
        beta[t] = (A @ (B[t + 1] * beta[t + 1])) / scale[t + 1]
    gamma = alpha * beta
    gamma /= gamma.sum(axis=1, keepdims=True)
    xi = (alpha[:-1, :, None] * A[None, :, :] * (B[1:] * beta[1:])[:, None, :]) / scale[1:, None, None]
    return alpha, gamma, xi, float(np.log(scale).sum())


def fit_hmm(x: np.ndarray, n_init: int = 5, max_iter: int = 200, tol: float = 1e-6, seed: int = 11) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    base_var = float(np.var(x))
    best = None
    for _ in range(n_init):
        mu = np.array([np.mean(x), np.mean(x)]) + rng.normal(0, np.sqrt(base_var) * 0.1, 2)
        var = np.array([0.5, 2.0]) * base_var * rng.uniform(0.7, 1.3, 2)
        stay = rng.uniform(0.85, 0.98, 2)
        A = np.array([[stay[0], 1 - stay[0]], [1 - stay[1], stay[1]]])
        pi = np.array([0.5, 0.5])
        previous = -np.inf
        for _ in range(max_iter):
            _, gamma, xi, ll = _forward_backward(x, pi, A, mu, var)
            pi = gamma[0]
            A = xi.sum(axis=0) / gamma[:-1].sum(axis=0)[:, None]
            A /= A.sum(axis=1, keepdims=True)
            weights = gamma.sum(axis=0)
            mu = (gamma * x[:, None]).sum(axis=0) / weights
            var = np.maximum((gamma * (x[:, None] - mu) ** 2).sum(axis=0) / weights, base_var * 1e-3)
            if abs(ll - previous) < tol:
                break
            previous = ll
        if best is None or ll > best["ll"]:
            best = {"ll": ll, "pi": pi, "A": A, "mu": mu, "var": var}
    order = np.argsort(best["var"])
    best["mu"], best["var"], best["pi"] = best["mu"][order], best["var"][order], best["pi"][order]
    best["A"] = best["A"][np.ix_(order, order)]
    return best


def regime_analysis(prices: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        series = log_returns(prices, minimum=120)
    except InsufficientData as exc:
        return {"status": "UNAVAILABLE", "message": str(exc)}
    x = series.to_numpy()
    fit = fit_hmm(x)
    alpha, gamma, _, ll = _forward_backward(x, fit["pi"], fit["A"], fit["mu"], fit["var"])

    T = len(x)
    ll_single = float(np.sum(-0.5 * np.log(2 * np.pi * x.var()) - 0.5 * (x - x.mean()) ** 2 / x.var()))
    bic_hmm = -2 * ll + 7 * math.log(T)          # 2 means, 2 variances, 2 transition probs, 1 initial prob
    bic_single = -2 * ll_single + 2 * math.log(T)
    significant = bic_hmm < bic_single

    labels = ["Low-volatility", "High-volatility"]
    states = []
    for i in range(2):
        persistence = float(fit["A"][i, i])
        states.append({
            "label": labels[i],
            "mean_daily": float(fit["mu"][i]),
            "annualized_return": float(fit["mu"][i] * 252),
            "annualized_volatility": float(math.sqrt(fit["var"][i] * 252)),
            "persistence": persistence,
            "expected_duration_days": 1 / (1 - persistence) if persistence < 1 else None,
            "share_of_days": float((gamma.argmax(axis=1) == i).mean()),
        })
    current = alpha[-1]
    current_state = int(np.argmax(current))
    vol_ratio = states[1]["annualized_volatility"] / states[0]["annualized_volatility"]
    return {
        "status": "VALID",
        "observations": T,
        "current_regime": labels[current_state],
        "current_probabilities": {labels[0]: float(current[0]), labels[1]: float(current[1])},
        "states": states,
        "transition_matrix": [[float(v) for v in row] for row in fit["A"]],
        "volatility_ratio": vol_ratio,
        "log_likelihood": ll,
        "bic_hmm": bic_hmm,
        "bic_single_regime": bic_single,
        "regimes_supported": significant,
        "sequence": [
            {"date": str(date.date()), "value": float(r), "p_high_vol": float(p)}
            for date, r, p in zip(series.index, x, gamma[:, 1])
        ],
        "methodology": "Two-state Gaussian hidden Markov model on daily log returns, estimated by Baum-Welch EM "
                       "(5 random starts). Current probabilities are filtered (use only data up to today); the "
                       "sequence chart shows smoothed probabilities. BIC compares against a single-regime model.",
    }
