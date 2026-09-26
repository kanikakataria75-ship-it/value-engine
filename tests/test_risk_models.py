"""Risk models validated on synthetic data with known answers."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from conftest import make_company
from mna_lbo_engine.modules.dcf_engine import DcfInputs
from mna_lbo_engine.modules.risk import credit, dependence, market_risk, regime, simulation
from mna_lbo_engine.modules.risk.factors import ols_hac
from mna_lbo_engine.modules.risk.returns import aligned_log_returns


def prices_from_returns(returns: np.ndarray, start: str = "2020-01-01", freq: str = "B") -> list[dict]:
    dates = pd.date_range(start, periods=len(returns) + 1, freq=freq)
    closes = 100 * np.cumprod(np.concatenate([[1.0], 1 + returns]))
    return [{"date": str(d.date()), "close": float(c)} for d, c in zip(dates, closes)]


def test_var_on_normal_returns_matches_theory():
    rng = np.random.default_rng(1)
    r = rng.normal(0.0005, 0.01, 20000)
    result = market_risk.value_at_risk(prices_from_returns(r))
    by = {(row["method"], row["confidence"]): row for row in result["table"]}
    theoretical = -(0.0005 + 0.01 * stats.norm.ppf(0.05))
    for method in ("historical", "normal", "cornish_fisher"):
        assert by[(method, 0.95)]["var_1d"] == pytest.approx(theoretical, rel=0.03)
    assert by[("normal", 0.99)]["es_1d"] > by[("normal", 0.99)]["var_1d"]
    assert result["normality_rejected"] is False


def test_cornish_fisher_widens_var_for_fat_tails():
    rng = np.random.default_rng(2)
    r = stats.t.rvs(df=3, size=5000, random_state=rng) * 0.006
    by = {(row["method"], row["confidence"]): row for row in market_risk.value_at_risk(prices_from_returns(r))["table"]}
    assert by[("cornish_fisher", 0.99)]["var_1d"] > by[("normal", 0.99)]["var_1d"]


def test_evt_detects_heavy_tail():
    rng = np.random.default_rng(3)
    r = stats.t.rvs(df=3, size=3000, random_state=rng) * 0.01
    result = market_risk.tail_risk_evt(prices_from_returns(r))
    assert result["status"] == "VALID" and result["shape_xi"] > 0.1
    assert result["levels"][0]["var_1d"] > result["threshold"]


def test_hmm_recovers_planted_volatility_regimes():
    rng = np.random.default_rng(4)
    calm, storm = rng.normal(0, 0.005, 200), rng.normal(0, 0.03, 100)
    result = regime.regime_analysis(prices_from_returns(np.concatenate([calm, storm, calm[:60]])))
    assert result["regimes_supported"] is True
    assert result["volatility_ratio"] > 3
    assert result["current_regime"] == "Low-volatility"
    storm_probs = [p["p_high_vol"] for p in result["sequence"][210:290]]
    assert np.mean(storm_probs) > 0.8


def test_hmm_on_a_single_regime_reports_no_structure():
    rng = np.random.default_rng(5)
    result = regime.regime_analysis(prices_from_returns(rng.normal(0, 0.01, 400)))
    assert result["regimes_supported"] is False


def test_merton_solution_satisfies_both_equations():
    solved = credit.solve_merton(equity=100.0, debt=300.0, sigma_e=0.45, r=0.04, horizon=1.0)
    v, s = solved["asset_value"], solved["asset_volatility"]
    d1 = (math.log(v / 300) + (0.04 + 0.5 * s * s)) / s
    d2 = d1 - s
    assert v * stats.norm.cdf(d1) - 300 * math.exp(-0.04) * stats.norm.cdf(d2) == pytest.approx(100.0, rel=1e-8)
    assert stats.norm.cdf(d1) * s * v == pytest.approx(0.45 * 100.0, rel=1e-8)
    assert solved["probability_of_default"] == pytest.approx(stats.norm.cdf(-solved["distance_to_default"]))


def test_merton_default_risk_rises_with_leverage():
    pds = [credit.solve_merton(100.0, debt, 0.4, 0.04)["probability_of_default"] for debt in (50.0, 200.0, 800.0)]
    assert pds[0] < pds[1] < pds[2]


def test_merton_uses_realised_volatility_and_handles_no_debt():
    rng = np.random.default_rng(6)
    prices = prices_from_returns(rng.normal(0, 0.02, 300))
    result = credit.merton_analysis(make_company(market_cap=100.0, total_debt=0.0), prices)
    assert result["probability_of_default"] == 0.0 and result["distance_to_default"] is None
    levered = credit.merton_analysis(make_company(market_cap=100.0, total_debt=100.0), prices)
    assert levered["inputs"]["equity_volatility"] == pytest.approx(0.02 * math.sqrt(252), rel=0.1)


def test_copula_recovers_dependence_and_aligns_calendars():
    rng = np.random.default_rng(7)
    z = rng.multivariate_normal([0, 0], [[1, 0.6], [0.6, 1]], size=600) * 0.01
    a = prices_from_returns(z[:, 0])
    b = prices_from_returns(z[:, 1])
    b_missing = [p for i, p in enumerate(b) if i % 10 != 5]      # a different holiday calendar
    result = dependence.copula_analysis(a, b_missing, "A", "B")
    assert result["status"] == "VALID"
    assert result["observations"] == len(aligned_log_returns(a, b_missing))
    assert result["kendall_tau"] == pytest.approx(2 / math.pi * math.asin(0.6), abs=0.08)
    assert result["joint_crash"]["multiple_of_independence"] > 2


def test_newey_west_ols_matches_statsmodels():
    sm = pytest.importorskip("statsmodels.api")
    rng = np.random.default_rng(8)
    x = rng.normal(size=(300, 2))
    y = 0.5 + x @ np.array([1.2, -0.4]) + rng.normal(size=300)
    X = np.column_stack([np.ones(300), x])
    ours = ols_hac(y, X, maxlags=5)
    ref = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    assert ours["beta"] == pytest.approx(ref.params, rel=1e-10)
    assert ours["se"] == pytest.approx(ref.bse, rel=1e-6)


def test_monte_carlo_downside_probability_uses_the_market_price(company):
    inputs = DcfInputs(revenue_growth=0.05, ebitda_margin=0.20, wacc=0.09, terminal_growth=0.02, tax_rate=0.25,
                       capex_pct=0.06, da_pct=0.05, nwc_pct=0.05, projection_years=5)
    result = simulation.run_monte_carlo(company, inputs, None, iterations=3000, seed=11)
    metrics = result["metrics"]
    assert result["status"] == "VALID" and result["current_price"] == company["current_price"]
    assert metrics["prob_below_market"] + metrics["prob_above_market"] == pytest.approx(1.0, abs=1e-3)
    swings = [row["swing"] for row in result["tornado"]]
    assert swings == sorted(swings, reverse=True)
    assert sum(row["variance_share"] for row in result["attribution"]) == pytest.approx(1.0)
    again = simulation.run_monte_carlo(company, inputs, None, iterations=3000, seed=11)
    assert again["metrics"] == metrics
