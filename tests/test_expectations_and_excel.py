"""Reverse DCF (Expectations Lab) round trips and Python-vs-Excel reconciliation."""
from __future__ import annotations

import warnings
from pathlib import Path

import openpyxl
import pytest

from conftest import make_bank, make_company
from mna_lbo_engine.modules.dcf_engine import DcfInputs, build_context, project, run_dcf
from mna_lbo_engine.modules.excel_exporter import build_workbook
from mna_lbo_engine.modules.expectations import expectations_analysis, financial_expectations, implied_drivers
from mna_lbo_engine.modules.financials_engine import ExcessReturnInputs, run_excess_return
from mna_lbo_engine.modules.lbo_engine import LboInputs, run_lbo_model
from mna_lbo_engine.modules.ma_engine import MnaInputs, run_ma_model

INPUTS = DcfInputs(revenue_growth=0.05, ebitda_margin=0.20, wacc=0.09, terminal_growth=0.02, tax_rate=0.25,
                   capex_pct=0.06, da_pct=0.05, nwc_pct=0.05, ronic=0.15, projection_years=5)


def test_implied_drivers_reprice_the_stock_exactly():
    company = make_company(current_price=14.0)
    ctx = build_context(company, INPUTS.tax_rate)
    implied = implied_drivers(ctx, INPUTS, 14.0)
    for key, arg in (("revenue_growth", "growth"), ("ebitda_margin", "margin"), ("expected_return", "wacc"),
                     ("terminal_growth", "terminal_growth")):
        assert implied[key] is not None
        price = project(ctx, INPUTS, **{arg: implied[key]})["price"][0]
        assert price == pytest.approx(14.0, rel=1e-6)


def test_frontier_points_all_justify_the_price():
    company = make_company(current_price=14.0)
    result = expectations_analysis(company, INPUTS, None)
    ctx = build_context(company, INPUTS.tax_rate)
    assert result["status"] == "VALID" and len(result["frontier"]) > 10
    for point in result["frontier"][::7]:
        price = project(ctx, INPUTS, growth=point["revenue_growth"], margin=point["required_margin"])["price"][0]
        assert price == pytest.approx(14.0, rel=1e-5)
    assert 0 <= result["odds_fundamentals_beat_price"] <= 1
    assert result["narrative"]


def test_unreachable_price_is_reported_not_forced():
    result = expectations_analysis(make_company(current_price=1e6), INPUTS, None)
    assert result["implied"]["revenue_growth"] is None
    assert "No growth rate" in result["narrative"][0]


def test_bank_implied_roe_closed_form():
    inputs = ExcessReturnInputs(roe=0.15, terminal_roe=0.15, cost_of_equity=0.10, book_growth=0.05,
                                terminal_growth=0.05, projection_years=5)
    result = financial_expectations(make_bank(current_price=15.0), inputs)
    assert result["implied_steady_state_roe"] == pytest.approx(0.05 + 1.5 * 0.05)


def _evaluate(path: Path) -> dict[str, object]:
    formulas = pytest.importorskip("formulas")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        solution = formulas.ExcelModel().loads(str(path)).finish().calculate()
    return {key.upper(): value.value[0][0] for key, value in solution.items() if hasattr(value, "value")}


def test_excel_formulas_reproduce_the_python_engine(tmp_path: Path):
    target = make_company()
    acquirer = make_company(ticker="ACQ", current_price=50.0, shares_outstanding=100.0, net_income=400.0,
                            cash_and_equivalents=300.0)
    dcf = run_dcf(target, INPUTS)
    lbo = run_lbo_model(target, LboInputs(entry_multiple=8.0, exit_multiple=9.0, senior_debt_turns=3.0, sub_debt_turns=1.0,
                                          senior_rate=0.08, sub_rate=0.11, revenue_growth=0.05, target_ebitda_margin=0.22,
                                          capex_pct=0.06, da_pct=0.05))
    mna = run_ma_model(acquirer, target, MnaInputs(pct_stock=0.4, pct_cash=0.2, pct_debt=0.4, cost_synergies=2.0), None)
    content = build_workbook({
        "company": target, "currency": "USD", "exported_at": "2026-09-26",
        "dcf": {"inputs": dcf["inputs"], "result": dcf}, "intrinsic_result": dcf,
        "lbo": {"result": lbo}, "mna": {"result": mna, "acquirer": acquirer, "target": target},
    })
    path = tmp_path / "model.xlsx"
    path.write_bytes(content)
    workbook = openpyxl.load_workbook(path)
    formula_cells = sum(1 for ws in workbook for row in ws.iter_rows() for c in row
                        if isinstance(c.value, str) and c.value.startswith("="))
    assert formula_cells > 150
    values = _evaluate(path)
    checks = workbook["Checks"]
    statuses = [values.get(f"'[MODEL.XLSX]CHECKS'!D{row}") for row in range(1, checks.max_row + 1)
                if str(checks.cell(row=row, column=4).value).startswith("=IF(ABS")]
    assert len(statuses) == 6
    assert all(status == "PASS" for status in statuses), statuses


def test_excel_excess_return_sheet_for_banks(tmp_path: Path):
    bank = make_bank()
    inputs = ExcessReturnInputs(roe=0.15, terminal_roe=0.12, cost_of_equity=0.10, book_growth=0.06, terminal_growth=0.04)
    result = run_excess_return(bank, inputs)
    path = tmp_path / "bank.xlsx"
    path.write_bytes(build_workbook({"company": bank, "currency": "INR", "exported_at": "x",
                                     "excess_return": {"inputs": result["inputs"], "result": result},
                                     "intrinsic_result": result}))
    values = _evaluate(path)
    workbook = openpyxl.load_workbook(path)
    checks = workbook["Checks"]
    statuses = [values.get(f"'[BANK.XLSX]CHECKS'!D{row}") for row in range(1, checks.max_row + 1)
                if str(checks.cell(row=row, column=4).value).startswith("=IF(ABS")]
    assert statuses == ["PASS", "PASS"]
    revenue_format = next(row[1].number_format for row in workbook["Assumptions"].iter_rows() if row[0].value == "Revenue")
    assert "₹" in revenue_format
