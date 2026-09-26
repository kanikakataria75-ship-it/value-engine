"""Intrinsic valuation engines: hand-computed golden values plus identities."""
from __future__ import annotations

import math
from dataclasses import replace

import pytest

from conftest import make_company
from mna_lbo_engine.modules.dcf_engine import DcfInputs, run_dcf, scenario_prices, build_context, sensitivity_grids
from mna_lbo_engine.modules.financials_engine import ExcessReturnInputs, run_excess_return

# Hand calculation (revenue 100, 10% growth, 20% margin, D&A 5%, CapEx 6%, NWC 10% of incremental revenue,
# tax 25%, WACC 10%, g 2%, RONIC 20%, two years, year-end discounting):
#   Y1  revenue 110   EBIT 16.5   NOPAT 12.375   UFCF 12.375 + 5.5 - 6.6 - 1.0  = 10.275   PV 9.3409090909
#   Y2  revenue 121   EBIT 18.15  NOPAT 13.6125  UFCF 13.6125 + 6.05 - 7.26 - 1.1 = 11.3025  PV 9.3409090909
#   TV  NOPAT(N+1) = 18.15 x 1.02 x 0.75 = 13.88475; FCF = 13.88475 x (1 - 0.02/0.20) = 12.496275
#       TV = 12.496275 / 0.08 = 156.2034375; PV = 129.09375
#   EV = 147.7755681818; equity = EV - 30 + 10 = 127.7755681818; price = 12.77755681818
GOLDEN = DcfInputs(revenue_growth=0.10, ebitda_margin=0.20, wacc=0.10, terminal_growth=0.02, tax_rate=0.25,
                   capex_pct=0.06, da_pct=0.05, nwc_pct=0.10, ronic=0.20, projection_years=2, mid_year_convention=False)


def test_dcf_matches_hand_calculation(company):
    result = run_dcf(company, GOLDEN)
    # terminal value is 87% of EV here, so the engine correctly asks for review
    assert result["status"] == "REVIEW_REQUIRED"
    assert {f["code"] for f in result["flags"]} == {"TV_DOMINANT"}
    assert result["terminal_share_of_ev"] == pytest.approx(129.09375 / 147.775568181818)
    ufcf = [row["ufcf"] for row in result["projections"]]
    assert ufcf == pytest.approx([10.275, 11.3025], rel=1e-12)
    assert result["pv_ufcf_sum"] == pytest.approx(18.681818181818, rel=1e-10)
    assert result["terminal_value"] == pytest.approx(156.2034375, rel=1e-12)
    assert result["pv_terminal_value"] == pytest.approx(129.09375, rel=1e-12)
    assert result["enterprise_value"] == pytest.approx(147.775568181818, rel=1e-10)
    assert result["implied_share_price"] == pytest.approx(12.7775568181818, rel=1e-10)
    assert result["upside"] == pytest.approx(0.27775568181818, rel=1e-9)


def test_mid_year_convention_shifts_every_cash_flow_by_half_a_year(company):
    end = run_dcf(company, GOLDEN)
    mid = run_dcf(company, replace(GOLDEN, mid_year_convention=True))
    assert mid["enterprise_value"] == pytest.approx(end["enterprise_value"] * math.sqrt(1.10), rel=1e-12)


def test_exit_multiple_is_discounted_at_year_end_even_with_mid_year(company):
    inputs = replace(GOLDEN, terminal_method="exit_multiple", exit_multiple=8.0, mid_year_convention=True)
    result = run_dcf(company, inputs)
    assert result["terminal_value"] == pytest.approx(24.2 * 8.0)
    assert result["pv_terminal_value"] == pytest.approx(160.0, rel=1e-12)


def test_margin_ramps_linearly_to_target(company):
    result = run_dcf(company, replace(GOLDEN, ebitda_margin=0.30))
    assert [row["ebitda_margin"] for row in result["projections"]] == pytest.approx([0.25, 0.30])


def test_value_falls_as_wacc_rises(company):
    ctx = build_context(company, GOLDEN.tax_rate)
    prices = scenario_prices(ctx, GOLDEN, wacc=[0.08, 0.09, 0.10, 0.11, 0.12])
    assert all(a > b for a, b in zip(prices, prices[1:]))


@pytest.mark.parametrize("change, message", [
    ({"wacc": 0.02, "terminal_growth": 0.03}, "strictly below WACC"),
    ({"projection_years": 0}, "Projection years"),
    ({"terminal_method": "exit_multiple", "exit_multiple": None}, "exit multiple"),
])
def test_invalid_assumptions_are_rejected_not_patched(company, change, message):
    result = run_dcf(company, replace(GOLDEN, **change))
    assert result["status"] == "INVALID" and message in result["message"]


@pytest.mark.parametrize("field", ["revenue", "shares_outstanding", "total_debt", "cash_and_equivalents"])
def test_missing_inputs_are_invalid_and_never_crash(field):
    result = run_dcf(make_company(**{field: None}), GOLDEN)
    assert result["status"] == "INVALID"


def test_diagnostics_flag_negative_equity_and_thin_spread(company):
    heavy_debt = run_dcf(make_company(total_debt=500.0), GOLDEN)
    assert "NEGATIVE_EQUITY" in {f["code"] for f in heavy_debt["flags"]}
    assert heavy_debt["status"] == "REVIEW_REQUIRED"
    thin = run_dcf(company, replace(GOLDEN, wacc=0.03))
    assert "THIN_SPREAD" in {f["code"] for f in thin["flags"]}


def test_sensitivity_centre_equals_base_case(company):
    grids = sensitivity_grids(company, GOLDEN)
    base = run_dcf(company, GOLDEN)["implied_share_price"]
    assert grids["wacc_terminal"][2][2] == pytest.approx(base)
    assert grids["growth_margin"][2][2] == pytest.approx(base)


# Residual income with constant ROE 15%, Ke 10%, book growth = g = 5% must equal the Gordon
# justified P/B = (ROE - g) / (Ke - g) = 2.0x, i.e. 20 per share on a book value of 10 per share.
ER = ExcessReturnInputs(roe=0.15, terminal_roe=0.15, cost_of_equity=0.10, book_growth=0.05, terminal_growth=0.05,
                        projection_years=2)


def test_residual_income_equals_justified_price_to_book(bank):
    result = run_excess_return(bank, ER)
    assert result["status"] == "VALID"
    assert [row["residual_income"] for row in result["schedule"]] == pytest.approx([5.0, 5.25])
    assert result["justified_pb"] == pytest.approx(2.0, rel=1e-12)
    assert result["implied_share_price"] == pytest.approx(20.0, rel=1e-12)


def test_roe_equal_to_cost_of_equity_is_worth_book(bank):
    result = run_excess_return(bank, replace(ER, roe=0.10, terminal_roe=0.10))
    assert result["justified_pb"] == pytest.approx(1.0, rel=1e-12)


def test_market_implied_roe_closed_form(bank):
    result = run_excess_return(bank, ER)
    # market P/B = 150 / 100 = 1.5 -> ROE* = g + P/B x (Ke - g) = 0.05 + 1.5 x 0.05
    assert result["market_implied_roe"] == pytest.approx(0.125)
