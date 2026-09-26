"""Data quality rules, baseline assumptions and classification."""
from __future__ import annotations

import pytest

from conftest import make_bank, make_company
from mna_lbo_engine.config import GROWTH_HISTORY_WEIGHT, market_parameters
from mna_lbo_engine.modules.assumptions import build_baseline, history_metrics, select_beta
from mna_lbo_engine.modules.common import is_balance_sheet_financial, reconcile_ebitda
from mna_lbo_engine.modules.data_quality_engine import ALL_FIELDS, run_data_quality_checks, summarize_quality


def rules(company):
    return {i["rule"]: i["severity"] for i in run_data_quality_checks(company)}


def test_every_field_missing_never_crashes():
    company = {"ticker": "EMPTY", **{field: None for field in ALL_FIELDS}}
    findings = rules(company)
    assert findings["MISSING_CORE_FIELD"] == "ERROR"
    assert summarize_quality(company, run_data_quality_checks(company))["status"] == "INVALID"


def test_ebit_above_ebitda_is_flagged_and_reconciled():
    assert rules(make_company(ebitda=10.0, ebit=15.0))["EBIT_EXCEEDS_EBITDA"] == "WARNING"
    assert reconcile_ebitda(10.0, 15.0, 5.0) == (20.0, True)
    assert reconcile_ebitda(25.0, 15.0, 5.0) == (25.0, False)
    assert reconcile_ebitda(None, 15.0, None) == (15.0, True)


def test_currency_mismatch_is_detected():
    assert rules(make_company(market_cap=100.0 * 80, revenue=100.0, net_income=10.0))["CURRENCY_MISMATCH_SUSPECTED"] == "WARNING"


def test_balance_sheet_identity():
    assert rules(make_company(total_assets=120.0, total_liabilities=70.0, book_equity=50.0))["BALANCE_SHEET_IDENTITY_OK"] == "INFO"
    assert rules(make_company(total_assets=200.0))["BALANCE_SHEET_IDENTITY"] == "WARNING"


def test_indian_provider_beta_is_never_used():
    findings = rules(make_company(currency="INR", beta=0.05))
    assert findings.get("PROVIDER_BETA_NOT_USED") == "INFO" and "BETA_OUT_OF_RANGE" not in findings
    beta, source = select_beta(make_company(currency="INR", beta=0.9), regression_beta=1.2)
    assert beta == pytest.approx(1.2) and "local market" in source


def test_us_beta_prefers_provider_and_falls_back_to_regression():
    assert select_beta(make_company(beta=1.1), regression_beta=0.7)[0] == pytest.approx(1.1)
    assert select_beta(make_company(beta=-0.1), regression_beta=0.7)[0] == pytest.approx(0.7)
    assert select_beta(make_company(beta=None), regression_beta=None) == (1.0, "market default (no valid beta available)")


HISTORY = [
    {"period_end": "2022-12-31", "revenue": 80.0, "ebitda": 15.0, "capex": 5.0, "d_and_a": 4.0},
    {"period_end": "2023-12-31", "revenue": 88.0, "ebitda": 17.0, "capex": 5.5, "d_and_a": 4.4},
    {"period_end": "2024-12-31", "revenue": 96.0, "ebitda": 19.0, "capex": 6.0, "d_and_a": 4.8},
    {"period_end": "2025-12-31", "revenue": 100.0, "ebitda": 20.0, "capex": 6.0, "d_and_a": 5.0},
]


def test_history_metrics():
    metrics = history_metrics(HISTORY)
    assert metrics["years"] == 4
    assert metrics["revenue_cagr"] == pytest.approx((100 / 80) ** (1 / 3) - 1)
    assert len(metrics["growth_series"]) == 3 and len(metrics["margin_series"]) == 4


def test_baseline_uses_the_companys_own_numbers():
    baseline = build_baseline(make_company(), HISTORY)
    cagr = (100 / 80) ** (1 / 3) - 1
    anchor = market_parameters("USD").growth_anchor
    assert baseline["dcf"]["ebitda_margin"] == pytest.approx(0.20)
    assert baseline["dcf"]["revenue_growth"] == pytest.approx(GROWTH_HISTORY_WEIGHT * cagr + (1 - GROWTH_HISTORY_WEIGHT) * anchor)
    assert baseline["dcf"]["terminal_growth"] < baseline["dcf"]["wacc"]
    assert baseline["lbo"]["target_ebitda_margin"] == pytest.approx(0.20)
    assert baseline["classification"]["intrinsic_model"] == "dcf"
    assert baseline["notes"]


def test_baseline_uses_local_market_parameters_for_india():
    baseline = build_baseline(make_company(ticker="X.NSE", currency="INR"), HISTORY, regression_beta=1.0)
    india = market_parameters("INR")
    assert baseline["wacc_build"]["risk_free_rate"] == india.risk_free_rate
    assert baseline["dcf"]["tax_rate"] == india.tax_rate


def test_banks_get_the_excess_return_model():
    baseline = build_baseline(make_bank(), [])
    assert baseline["classification"]["intrinsic_model"] == "excess_return"
    assert baseline["excess_return"]["roe"] == pytest.approx(0.15)
    assert baseline["lbo"] is None


@pytest.mark.parametrize("industry, assets, revenue, expected", [
    ("Banks - Regional", 1000, 50, True),
    ("Insurance - Life", 300, 100, True),
    ("Insurance Brokers", 500, 100, False),
    ("Credit Services", 250, 100, False),      # payment network
    ("Credit Services", 1200, 100, True),      # lender
    ("Financial Data & Stock Exchanges", 3000, 100, False),
    ("Asset Management", 5000, 100, True),     # holding company / NBFC
])
def test_financial_classification(industry, assets, revenue, expected):
    company = make_company(sector="Financial Services", industry=industry, total_assets=assets, revenue=revenue)
    assert is_balance_sheet_financial(company) is expected
