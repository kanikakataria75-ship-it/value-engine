import os
import sys
import pytest
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mna_lbo_engine.modules.data_loader import FinancialDataLoader
from mna_lbo_engine.modules.dcf_engine import run_dcf
from mna_lbo_engine.modules.ma_engine import run_ma_model
from mna_lbo_engine.modules.lbo_engine import run_lbo_model
from mna_lbo_engine.modules.comps_engine import run_trading_comps, run_transaction_comps
from mna_lbo_engine.modules.model_health import evaluate_model_health, calculate_deal_quality
from mna_lbo_engine.config import PRESET_FINANCIALS

@pytest.fixture
def base_target():
    return PRESET_FINANCIALS["AAPL"].copy()

@pytest.fixture
def base_acquirer():
    return PRESET_FINANCIALS["MSFT"].copy()

def test_1_default_application_calculation_path(base_target):
    res = run_dcf(base_target, 0.07, 0.25, 0.085, 0.025, 5, 0.21, False)
    assert res.get("status") == "VALID"
    assert res["implied_share_price"] > 0

def test_5_wacc_less_than_g(base_target):
    res = run_dcf(base_target, 0.07, 0.25, 0.02, 0.03, 5, 0.21, False)
    assert res.get("status") == "INVALID"
    assert "WACC" in res.get("message", "")

def test_9_ma_break_even_synergy(base_target, base_acquirer):
    # Dilutive deal requires synergies
    res = run_ma_model(base_acquirer, base_target, 0.25, 0.5, 0.5, 0.08, 0, 0.20, 0, 0, 0.21)
    req = res["break_even_pre_tax_synergy"]
    # Plug the required synergy back into revenue synergy (scaled by margin)
    rev_syn_needed = req / 0.20
    res_be = run_ma_model(base_acquirer, base_target, 0.25, 0.5, 0.5, 0.08, rev_syn_needed, 0.20, 0, 0, 0.21)
    np.testing.assert_almost_equal(res_be["eps_change_dollar"], 0.0, decimal=1)

def test_11_invalid_lbo_financing(base_target):
    res = run_lbo_model(base_target, 10.0, 0.8, 0.4, 0.08, 0.10, 11.0, 0.07, 0.25, 5, 0.21)
    # Debt sums to > 100% of EV
    assert res.get("status") == "INVALID"

def test_lbo_negative_cads_paydown(base_target):
    # Force negative CADS by applying extreme interest rate or margin collapse
    res = run_lbo_model(base_target, 10.0, 0.4, 0.2, 0.50, 0.50, 11.0, 0.0, 0.01, 5, 0.21)
    # The debt should not pay down below the initial balance (it will compound with PIK or just remain flat if no revolver)
    assert res.get("status") == "VALID"
    assert res["exit_debt"] >= res["total_debt_initial"]

def test_ma_invalid_consideration(base_target, base_acquirer):
    res = run_ma_model(base_acquirer, base_target, 0.25, 0.8, 0.8, 0.08, 0, 0.20, 0, 0, 0.21)
    assert res.get("status") == "INVALID"
    assert "100%" in res.get("message", "")

def test_12_13_zero_debt_zero_cash(base_target):
    edge = base_target.copy()
    edge["total_debt"] = 0
    edge["cash_and_equivalents"] = 0
    res = run_dcf(edge, 0.05, 0.20, 0.10, 0.03)
    assert res.get("status") == "VALID"
    assert res["net_debt"] == 0

def test_negative_debt_rejected(base_target):
    edge = base_target.copy()
    edge["total_debt"] = -50
    res = run_dcf(edge, 0.05, 0.20, 0.10, 0.03)
    assert res.get("status") == "INVALID"
    
def test_transaction_comps_unavailable(base_target):
    res = run_transaction_comps(base_target, [])
    assert res.get("status") == "UNAVAILABLE"
    
def test_model_health_dcf_invalid():
    dcf = {"status": "INVALID"}
    ma = {"status": "VALID"}
    lbo = {"status": "VALID"}
    health = evaluate_model_health(dcf, ma, lbo, [])
    assert health["status"] == "🔴 INVALID"
    
    dq = calculate_deal_quality(dcf, ma, lbo, {})
    assert dq["score"] == "UNAVAILABLE"

def test_ma_excel_export_does_not_fabricate(base_target, base_acquirer, tmp_path):
    from mna_lbo_engine.modules.excel_exporter import ExcelReportExporter
    exporter = ExcelReportExporter()
    ma_res = run_ma_model(base_acquirer, base_target, 0.25, 0.5, 0.5, 0.08, 10e6, 0.20, 5e6, 5e6, 0.21)
    
    # Intentionally strip out acquirer_net_income
    if "acquirer_net_income" in ma_res:
        del ma_res["acquirer_net_income"]
        
    filepath = str(tmp_path / "test_export.xlsx")
    exporter.export_full_model({"status": "VALID"}, ma_res, {"status": "VALID"}, filepath=filepath)
    
    import openpyxl
    wb = openpyxl.load_workbook(filepath)
    ws_ma = wb["5. M&A"]
    # Check that it didn't fabricate 0 but instead says UNAVAILABLE
    # We stripped it, so it should be UNAVAILABLE
    assert ws_ma["B3"].value == "UNAVAILABLE"

def test_ma_invalid_acquirer_aborts_engine():
    from mna_lbo_engine.modules.data_quality_engine import run_data_quality_checks
    bad_acquirer = {"ticker": "BAD", "revenue": -100} # Hard error
    dq = run_data_quality_checks(bad_acquirer)
    is_fatal = any(i["severity"] == "HARD ERROR" for i in dq)
    assert is_fatal is True

def test_17_missing_comps_data(base_target):
    # Should handle empty list gracefully
    res = run_trading_comps(base_target, [])
    assert res.get("status") == "UNAVAILABLE"
