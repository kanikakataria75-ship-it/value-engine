"""M&A, LBO and comps engines."""
from __future__ import annotations

from dataclasses import replace

import pytest

from conftest import make_bank, make_company
from mna_lbo_engine.modules.common import fmt_money
from mna_lbo_engine.modules.comps_engine import company_multiples, run_trading_comps, select_peers
from mna_lbo_engine.modules.fx import FxConverter, convert_company
from mna_lbo_engine.modules.lbo_engine import LboInputs, run_lbo_model
from mna_lbo_engine.modules.ma_engine import MnaInputs, run_ma_model


class StubFxStore:
    """INR per USD fixed at 80."""

    def get_fx_rate(self, pair, on_or_before=None):
        return {"pair": pair, "rate": 80.0, "date": "2026-09-01", "source": "test"} if pair == "USDINR" else None


ACQUIRER = make_company(ticker="ACQ", current_price=50.0, shares_outstanding=100.0, market_cap=5000.0, net_income=400.0,
                        cash_and_equivalents=300.0, ebitda=700.0)
TARGET = make_company(ticker="TGT", current_price=20.0, shares_outstanding=20.0, market_cap=400.0, net_income=30.0)


def test_break_even_synergies_restore_standalone_eps():
    expensive = {**TARGET, "net_income": 10.0}  # P/E paid of 50x makes the deal dilutive
    base = run_ma_model(ACQUIRER, expensive, MnaInputs(pct_stock=0.5, pct_cash=0.2, pct_debt=0.3), None)
    assert base["status"] in {"VALID", "REVIEW_REQUIRED"} and base["eps_change"] < 0
    needed = base["break_even_pre_tax_synergy"]
    balanced = run_ma_model(ACQUIRER, expensive, MnaInputs(pct_stock=0.5, pct_cash=0.2, pct_debt=0.3, cost_synergies=needed), None)
    assert balanced["eps_change"] == pytest.approx(0.0, abs=1e-12)


def test_foregone_interest_on_cash_is_charged():
    cash = run_ma_model(ACQUIRER, TARGET, MnaInputs(pct_stock=0.0, pct_cash=1.0, pct_debt=0.0, cash_yield=0.05, tax_rate=0.2), None)
    assert cash["foregone_interest_pre_tax"] == pytest.approx(TARGET["current_price"] * 1.25 * 20 * 0.05)
    assert cash["after_tax_financing_cost"] == pytest.approx(cash["foregone_interest_pre_tax"] * 0.8)


def test_ownership_splits_sum_to_one():
    result = run_ma_model(ACQUIRER, TARGET, MnaInputs(), None)
    assert result["ownership_acquirer"] + result["ownership_target"] == pytest.approx(1.0)


def test_consideration_mix_must_total_100_percent():
    result = run_ma_model(ACQUIRER, TARGET, MnaInputs(pct_stock=0.6, pct_cash=0.3, pct_debt=0.3), None)
    assert result["status"] == "INVALID" and "100%" in result["message"]


def test_cross_currency_target_is_converted_before_modelling():
    inr_target = make_company(ticker="TGT.NSE", currency="INR", current_price=20.0 * 80, shares_outstanding=20.0,
                              net_income=30.0 * 80, total_debt=30.0 * 80, cash_and_equivalents=10.0 * 80, ebitda=20.0 * 80)
    fx = FxConverter(StubFxStore())
    converted = run_ma_model(ACQUIRER, inr_target, MnaInputs(), fx)
    local = run_ma_model(ACQUIRER, TARGET, MnaInputs(), None)
    assert converted["fx"]["rate"] == pytest.approx(1 / 80)
    assert converted["new_shares_issued"] == pytest.approx(local["new_shares_issued"])
    assert converted["eps_change_pct"] == pytest.approx(local["eps_change_pct"])
    assert any(f["code"] == "FX_CONVERTED" for f in converted["flags"])


def test_cross_currency_without_fx_is_refused():
    inr_target = make_company(ticker="TGT.NSE", currency="INR")
    result = run_ma_model(ACQUIRER, inr_target, MnaInputs(), None)
    assert result["status"] == "INVALID"


def test_convert_company_restates_money_but_not_share_counts():
    quote = FxConverter(StubFxStore()).quote("INR", "USD")
    restated = convert_company(make_company(currency="INR", revenue=8000.0, shares_outstanding=10.0), quote)
    assert restated["revenue"] == pytest.approx(100.0) and restated["shares_outstanding"] == 10.0


LBO = LboInputs(entry_multiple=8.0, exit_multiple=8.0, senior_debt_turns=3.0, sub_debt_turns=1.0, senior_rate=0.08,
                sub_rate=0.11, revenue_growth=0.05, target_ebitda_margin=0.22, fees_pct=0.02, projection_years=5,
                tax_rate=0.25, capex_pct=0.04, da_pct=0.03, nwc_pct=0.05)


def test_lbo_sources_equal_uses_and_attribution_sums_to_value_creation(company):
    result = run_lbo_model(company, LBO)
    assert result["status"] in {"VALID", "REVIEW_REQUIRED"}
    assert result["total_uses"] == pytest.approx(result["senior_debt"] + result["sub_debt"] + result["sponsor_initial_equity"])
    assert sum(result["attribution"].values()) == pytest.approx(result["value_creation"], rel=1e-9)
    assert result["irr"] == pytest.approx(result["moic"] ** (1 / 5) - 1)


def test_lbo_margin_starts_from_actual_margin(company):
    result = run_lbo_model(company, LBO)
    first = result["schedule"][0]["ebitda_margin"]
    assert first == pytest.approx(0.20 + (0.22 - 0.20) / 5)


def test_lbo_cash_shortfalls_are_funded_by_the_revolver(company):
    result = run_lbo_model(company, replace(LBO, senior_rate=0.45, sub_rate=0.45, revenue_growth=-0.10))
    assert result["peak_revolver"] > 0
    assert any(f["code"] == "REVOLVER_DRAWN" for f in result["flags"])


def test_lbo_rejects_non_positive_sponsor_equity(company):
    result = run_lbo_model(company, replace(LBO, senior_debt_turns=8.0, sub_debt_turns=2.0))
    assert result["status"] == "INVALID"


def test_lbo_not_applicable_to_banks():
    assert run_lbo_model(make_bank(), LBO)["status"] == "INVALID"


def usd(amount, currency):
    return None if amount is None else (amount / 80 if currency == "INR" else amount)


def test_peer_selection_prefers_same_country_and_industry():
    target = make_company(ticker="T", industry="Machinery", market_cap=100.0)
    candidates = [
        make_company(ticker="SAME", industry="Machinery", market_cap=120.0),
        make_company(ticker="OTHER_IND", industry="Airlines", market_cap=100.0),
        make_company(ticker="INDIA", industry="Machinery", currency="INR", market_cap=100.0 * 80),
        make_bank(ticker="A_BANK"),
    ]
    order = [p["ticker"] for p in select_peers(target, candidates, usd)]
    assert order[0] == "SAME" and "A_BANK" not in order


def test_comps_implied_value_uses_median_multiple_and_net_debt():
    peers = [make_company(ticker=f"P{i}", market_cap=m, total_debt=0.0, cash_and_equivalents=0.0, ebitda=10.0)
             for i, m in enumerate([80.0, 100.0, 120.0])]
    result = run_trading_comps(make_company(), [{**p, "_score": 0} for p in peers])
    # median EV/EBITDA = 10x -> EV 200 -> equity 200 - 30 + 10 = 180 -> 18 per share
    assert result["primary_multiple"] == "ev_ebitda"
    assert result["implied_share_price_median"] == pytest.approx(18.0)


def test_banks_are_compared_on_price_to_book():
    assert company_multiples(make_bank())["ev_ebitda"] is None
    peers = [make_bank(ticker=f"B{i}", market_cap=m) for i, m in enumerate([90.0, 120.0, 150.0])]
    result = run_trading_comps(make_bank(), [{**p, "_score": 0} for p in peers])
    assert result["primary_multiple"] == "pb"


def test_flag_amounts_are_compact_and_in_the_acquirer_currency():
    assert fmt_money(1_481_123_857, "USD") == "$1.48B"
    assert fmt_money(2.5e12, "INR") == "₹2.50 L Cr"
    assert fmt_money(4.2e9, "INR") == "₹420 Cr"
    assert fmt_money(-3.2e6, "USD") == "-$3.20M"
