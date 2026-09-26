"""Excel export with live formulas.

Every model in the workbook is rebuilt from an Assumptions sheet with Excel formulas, so an
analyst can change a blue input and watch the model recalculate. A Checks sheet compares the
workbook's own results with the Python engine's results (they must agree to 1e-6).

Conventions: blue font = hard-coded input, black = formula. Sheet names avoid spaces and symbols
so formulas stay portable.
"""
from __future__ import annotations

from io import BytesIO
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..config import INPUT_BLUE_HEX, LIGHT_GRAY_HEX, NAVY_HEADER_HEX

HEADER_FILL = PatternFill(start_color=NAVY_HEADER_HEX, end_color=NAVY_HEADER_HEX, fill_type="solid")
SECTION_FILL = PatternFill(start_color=LIGHT_GRAY_HEX, end_color=LIGHT_GRAY_HEX, fill_type="solid")
WHITE_BOLD = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
TITLE = Font(name="Calibri", size=15, bold=True, color=NAVY_HEADER_HEX)
BOLD = Font(name="Calibri", size=11, bold=True)
INPUT = Font(name="Calibri", size=11, color=INPUT_BLUE_HEX)
NOTE = Font(name="Calibri", size=9, italic=True, color="666666")
THIN_TOP = Border(top=Side(style="thin", color="999999"))

PCT = "0.0%"
PCT2 = "0.00%"
MULT = '0.00"x"'
NUMBER = "#,##0"
DECIMAL = "0.0000"


def money_format(currency: str, decimals: int = 0) -> str:
    symbol = "₹" if currency == "INR" else "$"
    return f'"{symbol}"#,##0' + ("." + "0" * decimals if decimals else "")


class SheetWriter:
    """Writes label/value rows in columns A/B and remembers absolute addresses of named cells."""

    def __init__(self, ws: Any, refs: dict[str, str]) -> None:
        self.ws = ws
        self.refs = refs
        self.row = 1
        ws.column_dimensions["A"].width = 42
        ws.column_dimensions["B"].width = 20

    def addr(self, row: int, col: int = 2, absolute: bool = True) -> str:
        letter = get_column_letter(col)
        return f"{self.ws.title}!${letter}${row}" if absolute else f"{letter}{row}"

    def title(self, text: str, subtitle: str | None = None) -> None:
        self.ws.cell(row=self.row, column=1, value=text).font = TITLE
        self.row += 1
        if subtitle:
            self.ws.cell(row=self.row, column=1, value=subtitle).font = NOTE
            self.row += 1
        self.row += 1

    def section(self, text: str, width: int = 2) -> None:
        for col in range(1, width + 1):
            self.ws.cell(row=self.row, column=col).fill = HEADER_FILL
        self.ws.cell(row=self.row, column=1, value=text).font = WHITE_BOLD
        self.row += 1

    def put(self, label: str, value: Any, fmt: str | None = None, name: str | None = None,
            is_input: bool = False, bold: bool = False, note: str | None = None) -> str:
        self.ws.cell(row=self.row, column=1, value=label).font = BOLD if bold else Font(name="Calibri", size=11)
        cell = self.ws.cell(row=self.row, column=2, value=value)
        if fmt:
            cell.number_format = fmt
        if is_input:
            cell.font = INPUT
        elif bold:
            cell.font = BOLD
        if note:
            self.ws.cell(row=self.row, column=3, value=note).font = NOTE
        address = self.addr(self.row)
        if name:
            self.refs[name] = address
        self.row += 1
        return address

    def skip(self, rows: int = 1) -> None:
        self.row += rows


def _write_assumptions(wb: Any, refs: dict[str, str], payload: dict[str, Any]) -> None:
    company, currency = payload["company"], payload["currency"]
    w = SheetWriter(wb.create_sheet("Assumptions"), refs)
    money = money_format(currency)
    w.title("ASSUMPTIONS", "Blue cells are inputs: change them and every sheet recalculates.")
    w.section("Company data (latest fiscal year)")
    w.put("Revenue", company.get("revenue"), money, "revenue0", True)
    w.put("EBITDA", company.get("ebitda"), money, "ebitda0", True)
    w.put("Total debt", company.get("total_debt"), money, "debt", True)
    w.put("Cash & equivalents", company.get("cash_and_equivalents"), money, "cash", True)
    w.put("Book equity", company.get("book_equity"), money, "book", True)
    w.put("Shares outstanding", company.get("shares_outstanding"), NUMBER, "shares", True)
    w.put("Current share price", company.get("current_price"), money_format(currency, 2), "price", True)
    w.put("Current EBITDA margin", f"={refs['ebitda0']}/{refs['revenue0']}", PCT, "margin0")

    dcf = payload.get("dcf")
    if dcf:
        i = dcf["inputs"]
        w.skip()
        w.section("DCF assumptions")
        w.put("Revenue growth (annual)", i["revenue_growth"], PCT2, "g", True)
        w.put("Target EBITDA margin (final year)", i["ebitda_margin"], PCT2, "m_target", True)
        w.put("Margin ramp (1 = linear ramp, 0 = immediate)", 1 if i.get("margin_ramp", True) else 0, "0", "ramp", True)
        w.put("D&A (% of revenue)", i["da_pct"], PCT2, "da_pct", True)
        w.put("CapEx (% of revenue)", i["capex_pct"], PCT2, "capex_pct", True)
        w.put("Change in NWC (% of incremental revenue)", i["nwc_pct"], PCT2, "nwc_pct", True)
        w.put("Tax rate", i["tax_rate"], PCT2, "tax", True)
        w.put("WACC", i["wacc"], PCT2, "wacc", True)
        w.put("Terminal growth", i["terminal_growth"], PCT2, "tg", True)
        w.put("Return on new invested capital (terminal)", i["ronic"], PCT2, "ronic", True)
        w.put("Mid-year convention (1 = yes)", 1 if i["mid_year_convention"] else 0, "0", "mid", True)
        w.put("Exit EV/EBITDA multiple (exit-multiple method)", i.get("exit_multiple") or 0, MULT, "exit_multiple", True)
        w.put("Terminal method", i["terminal_method"], None, "tv_method", True,
              note="perpetuity = value-driver formula; exit_multiple = EBITDA x multiple")

    er = payload.get("excess_return")
    if er:
        i = er["inputs"]
        w.skip()
        w.section("Excess-return (residual income) assumptions")
        w.put("Current ROE", i["roe"], PCT2, "roe", True)
        w.put("Terminal ROE (year N)", i["terminal_roe"], PCT2, "troe", True)
        w.put("Cost of equity", i["cost_of_equity"], PCT2, "ke", True)
        w.put("Book value growth", i["book_growth"], PCT2, "bg", True)
        w.put("Terminal growth", i["terminal_growth"], PCT2, "er_g", True)

    notes = payload.get("baseline_notes") or []
    if notes:
        w.skip()
        w.section("How the baseline was built")
        for note in notes:
            w.ws.cell(row=w.row, column=1, value=note).font = NOTE
            w.row += 1


def _write_dcf(wb: Any, refs: dict[str, str], payload: dict[str, Any]) -> None:
    dcf, currency = payload["dcf"], payload["currency"]
    n = int(dcf["inputs"]["projection_years"])
    ws = wb.create_sheet("DCF")
    ws.column_dimensions["A"].width = 34
    money = money_format(currency)
    ws["A1"] = "DISCOUNTED CASH FLOW"
    ws["A1"].font = TITLE
    ws["A2"] = f"All figures in {currency}. Year 0 = latest fiscal year."
    ws["A2"].font = NOTE
    header_row = 4
    ws.cell(row=header_row, column=1, value="Year").font = WHITE_BOLD
    ws.cell(row=header_row, column=1).fill = HEADER_FILL
    for t in range(0, n + 1):
        cell = ws.cell(row=header_row, column=2 + t, value=t)
        cell.font, cell.fill = WHITE_BOLD, HEADER_FILL
        ws.column_dimensions[get_column_letter(2 + t)].width = 16
    rows = ["Revenue", "EBITDA margin", "EBITDA", "D&A", "EBIT", "Taxes", "NOPAT", "CapEx", "Change in NWC",
            "Unlevered FCF", "Discount period", "Discount factor", "PV of UFCF"]
    r = {name: header_row + 1 + idx for idx, name in enumerate(rows)}
    for name, row in r.items():
        ws.cell(row=row, column=1, value=name)
    ws.cell(row=r["Unlevered FCF"], column=1).font = BOLD

    col = lambda t: get_column_letter(2 + t)  # noqa: E731
    ws[f"B{r['Revenue']}"] = f"={refs['revenue0']}"
    ws[f"B{r['EBITDA margin']}"] = f"={refs['margin0']}"
    ws[f"B{r['EBITDA']}"] = f"={refs['ebitda0']}"
    for t in range(1, n + 1):
        c, p = col(t), col(t - 1)
        ws[f"{c}{r['Revenue']}"] = f"={p}{r['Revenue']}*(1+{refs['g']})"
        ws[f"{c}{r['EBITDA margin']}"] = (f"=IF({refs['ramp']}=1,{refs['margin0']}+({refs['m_target']}-{refs['margin0']})*{t}/{n},"
                                         f"{refs['m_target']})")
        ws[f"{c}{r['EBITDA']}"] = f"={c}{r['Revenue']}*{c}{r['EBITDA margin']}"
        ws[f"{c}{r['D&A']}"] = f"={c}{r['Revenue']}*{refs['da_pct']}"
        ws[f"{c}{r['EBIT']}"] = f"={c}{r['EBITDA']}-{c}{r['D&A']}"
        ws[f"{c}{r['Taxes']}"] = f"=MAX({c}{r['EBIT']},0)*{refs['tax']}"
        ws[f"{c}{r['NOPAT']}"] = f"={c}{r['EBIT']}-{c}{r['Taxes']}"
        ws[f"{c}{r['CapEx']}"] = f"={c}{r['Revenue']}*{refs['capex_pct']}"
        ws[f"{c}{r['Change in NWC']}"] = f"=({c}{r['Revenue']}-{p}{r['Revenue']})*{refs['nwc_pct']}"
        ws[f"{c}{r['Unlevered FCF']}"] = f"={c}{r['NOPAT']}+{c}{r['D&A']}-{c}{r['CapEx']}-{c}{r['Change in NWC']}"
        ws[f"{c}{r['Discount period']}"] = f"={t}-0.5*{refs['mid']}"
        ws[f"{c}{r['Discount factor']}"] = f"=1/(1+{refs['wacc']})^{c}{r['Discount period']}"
        ws[f"{c}{r['PV of UFCF']}"] = f"={c}{r['Unlevered FCF']}*{c}{r['Discount factor']}"
    for name in rows:
        fmt = PCT if name == "EBITDA margin" else DECIMAL if name in {"Discount factor"} else "0.0" if name == "Discount period" else money
        for t in range(0, n + 1):
            ws.cell(row=r[name], column=2 + t).number_format = fmt

    last = col(n)
    s = r["PV of UFCF"] + 2
    labels = [
        ("Sum of PV of UFCF", f"=SUM({col(1)}{r['PV of UFCF']}:{last}{r['PV of UFCF']})", money, "sum_pv"),
        ("Terminal-year NOPAT (N+1)", f"={last}{r['EBIT']}*(1+{refs['tg']})-MAX({last}{r['EBIT']}*(1+{refs['tg']}),0)*{refs['tax']}", money, "nopat_next"),
        ("Effective RONIC", f"=MAX({refs['ronic']},{refs['tg']}+0.01)", PCT2, "ronic_eff"),
        ("Normalised terminal FCF", "={nopat_next}*(1-{tg}/{ronic_eff})", money, "tv_fcf"),
        ("Terminal value", f"=IF({refs['tv_method']}=\"exit_multiple\",{last}{r['EBITDA']}*{refs['exit_multiple']},"
                           "{tv_fcf}/({wacc}-{tg}))", money, "tv"),
        ("Terminal discount period", f"=IF({refs['tv_method']}=\"exit_multiple\",{n},{n}-0.5*{refs['mid']})", "0.0", "tv_period"),
        ("PV of terminal value", "={tv}/(1+{wacc})^{tv_period}", money, "pv_tv"),
        ("Enterprise value", "={sum_pv}+{pv_tv}", money, "ev"),
        ("Less: total debt", f"={refs['debt']}", money, None),
        ("Plus: cash", f"={refs['cash']}", money, None),
        ("Equity value", f"={{ev}}-{refs['debt']}+{refs['cash']}", money, "equity"),
        ("Implied share price", f"={{equity}}/{refs['shares']}", money_format(currency, 2), "dcf_price"),
        ("Upside / (downside) vs. market", f"={{dcf_price}}/{refs['price']}-1", PCT, "dcf_upside"),
        ("Terminal value share of EV", "={pv_tv}/{ev}", PCT, "tv_share"),
    ]
    for offset, (label, formula, fmt, name) in enumerate(labels):
        row = s + offset
        ws.cell(row=row, column=1, value=label).font = BOLD if name in {"ev", "equity", "dcf_price"} else Font(name="Calibri", size=11)
        local_refs = {k: v for k, v in refs.items()}
        cell = ws.cell(row=row, column=2, value=formula.format(**local_refs) if "{" in formula else formula)
        cell.number_format = fmt
        if name:
            refs[name] = f"DCF!$B${row}"


def _write_excess_return(wb: Any, refs: dict[str, str], payload: dict[str, Any]) -> None:
    er, currency = payload["excess_return"], payload["currency"]
    n = int(er["inputs"]["projection_years"])
    w = SheetWriter(wb.create_sheet("ExcessReturn"), refs)
    ws = w.ws
    money = money_format(currency)
    w.title("EXCESS-RETURN (RESIDUAL INCOME) VALUATION", "For banks, insurers and lenders: value = book equity + PV of returns above the cost of equity.")
    header = w.row
    for c, text in enumerate(["Year", "Opening book", "ROE", "Net income", "Equity charge", "Residual income", "Closing book", "PV of RI"], start=1):
        cell = ws.cell(row=header, column=c, value=text)
        cell.font, cell.fill = WHITE_BOLD, HEADER_FILL
        ws.column_dimensions[get_column_letter(c)].width = 18
    for t in range(1, n + 1):
        row = header + t
        prev_close = f"G{row - 1}" if t > 1 else refs["book"]
        ws.cell(row=row, column=1, value=t)
        ws.cell(row=row, column=2, value=f"={prev_close}").number_format = money
        ws.cell(row=row, column=3, value=f"={refs['roe']}+({refs['troe']}-{refs['roe']})*{t}/{n}").number_format = PCT2
        ws.cell(row=row, column=4, value=f"=C{row}*B{row}").number_format = money
        ws.cell(row=row, column=5, value=f"={refs['ke']}*B{row}").number_format = money
        ws.cell(row=row, column=6, value=f"=D{row}-E{row}").number_format = money
        ws.cell(row=row, column=7, value=f"=B{row}*(1+{refs['bg']})").number_format = money
        ws.cell(row=row, column=8, value=f"=F{row}/(1+{refs['ke']})^A{row}").number_format = money
    last = header + n
    w.row = last + 2
    w.put("Sum of PV of residual income", f"=SUM(H{header + 1}:H{last})", money, "er_sum")
    w.put("Terminal value", f"=({refs['troe']}-{refs['ke']})*G{last}/({refs['ke']}-{refs['er_g']})", money, "er_tv")
    w.put("PV of terminal value", f"={refs['er_tv']}/(1+{refs['ke']})^{n}", money, "er_pv_tv")
    w.put("Equity value", f"={refs['book']}+{refs['er_sum']}+{refs['er_pv_tv']}", money, "equity", bold=True)
    w.put("Implied share price", f"={refs['equity']}/{refs['shares']}", money_format(currency, 2), "dcf_price", bold=True)
    w.put("Upside / (downside) vs. market", f"={refs['dcf_price']}/{refs['price']}-1", PCT, "dcf_upside")
    w.put("Justified P/B", f"={refs['equity']}/{refs['book']}", MULT, "justified_pb")


def _write_sensitivity(wb: Any, payload: dict[str, Any]) -> None:
    grids = payload.get("sensitivity")
    if not grids or grids.get("status") != "VALID":
        return
    ws = wb.create_sheet("Sensitivity")
    ws["A1"] = "SENSITIVITY TABLES (values computed by the ValuEngine engine; static)"
    ws["A1"].font = TITLE
    fmt = money_format(payload["currency"], 2)
    row = 3

    def table(title: str, row_label: str, col_label: str, rows: list[float], cols: list[float], values: list[list[Any]]) -> None:
        nonlocal row
        ws.cell(row=row, column=1, value=title).font = BOLD
        row += 1
        ws.cell(row=row, column=1, value=f"{row_label} \\ {col_label}").font = NOTE
        for j, c in enumerate(cols):
            cell = ws.cell(row=row, column=2 + j, value=c)
            cell.number_format, cell.font, cell.fill = PCT, WHITE_BOLD, HEADER_FILL
        for i, rv in enumerate(rows):
            ws.cell(row=row + 1 + i, column=1, value=rv).number_format = PCT
            for j, value in enumerate(values[i]):
                ws.cell(row=row + 1 + i, column=2 + j, value=value).number_format = fmt
        row += len(rows) + 3

    if "wacc_terminal" in grids:
        table("Implied share price: terminal growth (rows) x WACC (columns)", "Terminal growth", "WACC",
              grids["terminal_growth_values"], grids["wacc_values"], grids["wacc_terminal"])
        table("Implied share price: EBITDA margin (rows) x revenue growth (columns)", "Margin", "Growth",
              grids["ebitda_margin_values"], grids["revenue_growth_values"], grids["growth_margin"])
    elif "ke_growth" in grids:
        table("Implied share price: terminal growth (rows) x cost of equity (columns)", "Growth", "Ke",
              grids["terminal_growth_values"], grids["cost_of_equity_values"], grids["ke_growth"])
        table("Implied share price: terminal ROE (rows) x cost of equity (columns)", "ROE", "Ke",
              grids["terminal_roe_values"], grids["cost_of_equity_values"], grids["ke_roe"])
    for c in range(1, 8):
        ws.column_dimensions[get_column_letter(c)].width = 16


def _write_accretion(wb: Any, refs: dict[str, str], payload: dict[str, Any]) -> None:
    mna = payload["mna"]
    result, inputs = mna["result"], mna["result"]["inputs"]
    acquirer, target = mna["acquirer"], mna["target"]
    currency = result["currency"]
    w = SheetWriter(wb.create_sheet("Accretion"), refs)
    money, money2 = money_format(currency), money_format(currency, 2)
    fx = (result.get("fx") or {}).get("rate", 1.0)
    w.title("M&A ACCRETION / DILUTION", f"{result['acquirer_ticker']} acquiring {result['target_ticker']}; figures in {currency}.")
    w.section("Acquirer")
    w.put("Share price", acquirer.get("current_price"), money2, "a_price", True)
    w.put("Shares outstanding", acquirer.get("shares_outstanding"), NUMBER, "a_shares", True)
    w.put("Net income", acquirer.get("net_income"), money, "a_ni", True)
    w.skip()
    w.section(f"Target (reported in {result['target_currency']})")
    w.put(f"FX rate ({currency} per {result['target_currency']})", fx, "0.000000", "fx", True)
    w.put(f"Share price ({result['target_currency']})", target.get("current_price"), None, "t_price_local", True)
    w.put("Shares outstanding", target.get("shares_outstanding"), NUMBER, "t_shares", True)
    w.put(f"Net income ({result['target_currency']})", target.get("net_income"), None, "t_ni_local", True)
    w.put(f"Share price ({currency})", f"={refs['t_price_local']}*{refs['fx']}", money2, "t_price")
    w.put(f"Net income ({currency})", f"={refs['t_ni_local']}*{refs['fx']}", money, "t_ni")
    w.skip()
    w.section("Deal terms")
    w.put("Offer premium", inputs["offer_premium_pct"], PCT, "premium", True)
    w.put("% paid in new acquirer shares", inputs["pct_stock"], PCT, "p_stock", True)
    w.put("% paid from cash on hand", inputs["pct_cash"], PCT, "p_cash", True)
    w.put("% funded with new debt", inputs["pct_debt"], PCT, "p_debt", True)
    w.put("Interest rate on new debt", inputs["debt_interest_rate"], PCT2, "debt_rate", True)
    w.put("Yield forgone on cash used", inputs["cash_yield"], PCT2, "cash_yield", True)
    w.put("Revenue synergies (run-rate)", inputs["revenue_synergies"], money, "rev_syn", True)
    w.put("Margin on revenue synergies", inputs["incremental_margin"], PCT, "syn_margin", True)
    w.put("Cost synergies (run-rate)", inputs["cost_synergies"], money, "cost_syn", True)
    w.put("One-off integration costs (year 1)", inputs["integration_costs"], money, "integration", True)
    w.put("Tax rate", inputs["tax_rate"], PCT, "m_tax", True)
    w.skip()
    w.section("Pro forma")
    w.put("Offer price per share", f"={refs['t_price']}*(1+{refs['premium']})", money2, "offer")
    w.put("Purchase equity value", f"={refs['offer']}*{refs['t_shares']}", money, "purchase")
    w.put("New shares issued", f"={refs['purchase']}*{refs['p_stock']}/{refs['a_price']}", NUMBER, "new_shares")
    w.put("After-tax financing cost", f"=({refs['purchase']}*{refs['p_debt']}*{refs['debt_rate']}+{refs['purchase']}*{refs['p_cash']}*{refs['cash_yield']})*(1-{refs['m_tax']})", money, "fin_cost")
    w.put("After-tax synergies", f"=({refs['rev_syn']}*{refs['syn_margin']}+{refs['cost_syn']})*(1-{refs['m_tax']})", money, "at_syn")
    w.put("After-tax integration costs", f"={refs['integration']}*(1-{refs['m_tax']})", money, "at_integ")
    w.put("Pro forma net income (run-rate)", f"={refs['a_ni']}+{refs['t_ni']}+{refs['at_syn']}-{refs['fin_cost']}", money, "pf_ni_rr")
    w.put("Pro forma net income (year 1)", f"={refs['pf_ni_rr']}-{refs['at_integ']}", money, "pf_ni")
    w.put("Pro forma shares", f"={refs['a_shares']}+{refs['new_shares']}", NUMBER, "pf_shares")
    w.put("Standalone EPS", f"={refs['a_ni']}/{refs['a_shares']}", money2, "eps0")
    w.put("Pro forma EPS (year 1)", f"={refs['pf_ni']}/{refs['pf_shares']}", money2, "eps1", bold=True)
    w.put("Accretion / (dilution), year 1", f"={refs['eps1']}/{refs['eps0']}-1", PCT2, "accretion", bold=True)
    w.put("Pro forma EPS (run-rate)", f"={refs['pf_ni_rr']}/{refs['pf_shares']}", money2, "eps_rr")
    w.put("Break-even pre-tax synergies", f"=MAX({refs['eps0']}*{refs['pf_shares']}-({refs['a_ni']}+{refs['t_ni']}-{refs['fin_cost']}-{refs['at_integ']}),0)/(1-{refs['m_tax']})", money, "break_even")
    w.put("Target shareholders' ownership", f"={refs['new_shares']}/{refs['pf_shares']}", PCT, "own_target")


def _write_lbo(wb: Any, refs: dict[str, str], payload: dict[str, Any]) -> None:
    lbo, currency = payload["lbo"]["result"], payload["currency"]
    i = lbo["inputs"]
    n = int(i["projection_years"])
    ws = wb.create_sheet("LBO")
    w = SheetWriter(ws, refs)
    money = money_format(currency)
    w.title("LEVERAGED BUYOUT", f"Figures in {currency}. Debt sized in turns of entry EBITDA; shortfalls funded by a revolver.")
    w.section("Inputs")
    w.put("Entry EV / EBITDA", i["entry_multiple"], MULT, "l_entry", True)
    w.put("Exit EV / EBITDA", i["exit_multiple"], MULT, "l_exit", True)
    w.put("Senior debt (x EBITDA)", i["senior_debt_turns"], MULT, "l_snr_x", True)
    w.put("Subordinated debt (x EBITDA)", i["sub_debt_turns"], MULT, "l_sub_x", True)
    w.put("Senior rate", i["senior_rate"], PCT2, "l_snr_r", True)
    w.put("Subordinated rate", i["sub_rate"], PCT2, "l_sub_r", True)
    w.put("Revolver rate", i["revolver_rate"], PCT2, "l_rev_r", True)
    w.put("Senior mandatory amortisation (% of original)", i["senior_amortization"], PCT, "l_amort", True)
    w.put("Revenue growth", i["revenue_growth"], PCT2, "l_g", True)
    w.put("Target EBITDA margin (exit year)", i["target_ebitda_margin"], PCT2, "l_m", True)
    w.put("Transaction fees (% of EV)", i["fees_pct"], PCT, "l_fees", True)
    w.put("Tax rate", i["tax_rate"], PCT, "l_tax", True)
    w.put("CapEx (% of revenue)", i["capex_pct"], PCT2, "l_capex", True)
    w.put("D&A (% of revenue)", i["da_pct"], PCT2, "l_da", True)
    w.put("Change in NWC (% of incremental revenue)", i["nwc_pct"], PCT2, "l_nwc", True)
    w.skip()
    w.section("Sources & uses")
    w.put("Entry enterprise value", f"={refs['ebitda0']}*{refs['l_entry']}", money, "l_ev")
    w.put("Transaction fees", f"={refs['l_ev']}*{refs['l_fees']}", money, "l_fee_amt")
    w.put("Total uses", f"={refs['l_ev']}+{refs['l_fee_amt']}", money, "l_uses", bold=True)
    w.put("Senior debt", f"={refs['ebitda0']}*{refs['l_snr_x']}", money, "l_snr0")
    w.put("Subordinated debt", f"={refs['ebitda0']}*{refs['l_sub_x']}", money, "l_sub0")
    w.put("Sponsor equity", f"={refs['l_uses']}-{refs['l_snr0']}-{refs['l_sub0']}", money, "l_eq0", bold=True)
    w.skip()

    top = w.row
    ws.cell(row=top, column=1, value="Year").font = WHITE_BOLD
    ws.cell(row=top, column=1).fill = HEADER_FILL
    for t in range(0, n + 1):
        cell = ws.cell(row=top, column=2 + t, value=t)
        cell.font, cell.fill = WHITE_BOLD, HEADER_FILL
        ws.column_dimensions[get_column_letter(2 + t)].width = 16
    names = ["Revenue", "EBITDA margin", "EBITDA", "D&A", "EBIT", "Interest", "Taxes", "CapEx", "Change in NWC",
             "Levered FCF", "Mandatory amortisation", "Cash after mandatory", "Cash used for shortfall",
             "Revolver draw", "Revolver repayment", "Senior sweep", "Subordinated sweep",
             "Senior debt (end)", "Subordinated debt (end)", "Revolver (end)", "Cash (end)", "Net debt (end)"]
    r = {name: top + 1 + k for k, name in enumerate(names)}
    for name, row in r.items():
        ws.cell(row=row, column=1, value=name)
    col = lambda t: get_column_letter(2 + t)  # noqa: E731
    ws[f"B{r['Revenue']}"] = f"={refs['revenue0']}"
    ws[f"B{r['EBITDA']}"] = f"={refs['ebitda0']}"
    ws[f"B{r['Senior debt (end)']}"] = f"={refs['l_snr0']}"
    ws[f"B{r['Subordinated debt (end)']}"] = f"={refs['l_sub0']}"
    ws[f"B{r['Revolver (end)']}"] = 0
    ws[f"B{r['Cash (end)']}"] = 0
    ws[f"B{r['Net debt (end)']}"] = f"=B{r['Senior debt (end)']}+B{r['Subordinated debt (end)']}+B{r['Revolver (end)']}-B{r['Cash (end)']}"
    for t in range(1, n + 1):
        c, p = col(t), col(t - 1)
        avail = f"{c}{r['Cash after mandatory']}"
        f = {
            "Revenue": f"={p}{r['Revenue']}*(1+{refs['l_g']})",
            "EBITDA margin": f"={refs['margin0']}+({refs['l_m']}-{refs['margin0']})*{t}/{n}",
            "EBITDA": f"={c}{r['Revenue']}*{c}{r['EBITDA margin']}",
            "D&A": f"={c}{r['Revenue']}*{refs['l_da']}",
            "EBIT": f"={c}{r['EBITDA']}-{c}{r['D&A']}",
            "Interest": f"={p}{r['Senior debt (end)']}*{refs['l_snr_r']}+{p}{r['Subordinated debt (end)']}*{refs['l_sub_r']}+{p}{r['Revolver (end)']}*{refs['l_rev_r']}",
            "Taxes": f"=MAX({c}{r['EBIT']}-{c}{r['Interest']},0)*{refs['l_tax']}",
            "CapEx": f"={c}{r['Revenue']}*{refs['l_capex']}",
            "Change in NWC": f"=({c}{r['Revenue']}-{p}{r['Revenue']})*{refs['l_nwc']}",
            "Levered FCF": f"={c}{r['EBITDA']}-{c}{r['Taxes']}-{c}{r['CapEx']}-{c}{r['Change in NWC']}-{c}{r['Interest']}",
            "Mandatory amortisation": f"=MIN({p}{r['Senior debt (end)']},{refs['l_snr0']}*{refs['l_amort']})",
            "Cash after mandatory": f"={c}{r['Levered FCF']}-{c}{r['Mandatory amortisation']}",
            "Cash used for shortfall": f"=IF({avail}<0,MIN({p}{r['Cash (end)']},-{avail}),0)",
            "Revolver draw": f"=IF({avail}<0,-{avail}-{c}{r['Cash used for shortfall']},0)",
            "Revolver repayment": f"=IF({avail}>0,MIN({p}{r['Revolver (end)']},{avail}),0)",
            "Senior sweep": f"=IF({avail}>0,MIN({p}{r['Senior debt (end)']}-{c}{r['Mandatory amortisation']},{avail}-{c}{r['Revolver repayment']}),0)",
            "Subordinated sweep": f"=IF({avail}>0,MIN({p}{r['Subordinated debt (end)']},{avail}-{c}{r['Revolver repayment']}-{c}{r['Senior sweep']}),0)",
            "Senior debt (end)": f"={p}{r['Senior debt (end)']}-{c}{r['Mandatory amortisation']}-{c}{r['Senior sweep']}",
            "Subordinated debt (end)": f"={p}{r['Subordinated debt (end)']}-{c}{r['Subordinated sweep']}",
            "Revolver (end)": f"={p}{r['Revolver (end)']}+{c}{r['Revolver draw']}-{c}{r['Revolver repayment']}",
            "Cash (end)": f"={p}{r['Cash (end)']}-{c}{r['Cash used for shortfall']}+IF({avail}>0,{avail}-{c}{r['Revolver repayment']}-{c}{r['Senior sweep']}-{c}{r['Subordinated sweep']},0)",
            "Net debt (end)": f"={c}{r['Senior debt (end)']}+{c}{r['Subordinated debt (end)']}+{c}{r['Revolver (end)']}-{c}{r['Cash (end)']}",
        }
        for name, formula in f.items():
            ws[f"{c}{r[name]}"] = formula
    for name, row in r.items():
        for t in range(0, n + 1):
            ws.cell(row=row, column=2 + t).number_format = PCT if name == "EBITDA margin" else money
    last = col(n)
    w.row = r["Net debt (end)"] + 2
    w.section("Returns")
    w.put("Exit EBITDA", f"={last}{r['EBITDA']}", money, "l_exit_ebitda")
    w.put("Exit enterprise value", f"={refs['l_exit_ebitda']}*{refs['l_exit']}", money, "l_exit_ev")
    w.put("Exit equity value", f"=MAX({refs['l_exit_ev']}-{last}{r['Net debt (end)']},0)", money, "l_exit_eq", bold=True)
    w.put("MOIC", f"={refs['l_exit_eq']}/{refs['l_eq0']}", MULT, "l_moic", bold=True)
    w.put("IRR", f"=IF({refs['l_moic']}>0,{refs['l_moic']}^(1/{n})-1,-1)", PCT2, "l_irr", bold=True)
    flow_row = w.row + 1
    ws.cell(row=flow_row, column=1, value="Sponsor cash flows (for =IRR)")
    for t in range(0, n + 1):
        value = f"=-{refs['l_eq0']}" if t == 0 else (f"={refs['l_exit_eq']}" if t == n else 0)
        ws.cell(row=flow_row, column=2 + t, value=value).number_format = money
    w.row = flow_row + 1
    w.put("IRR (Excel =IRR on the cash flows)", f"=IFERROR(IRR(B{flow_row}:{last}{flow_row}),-1)", PCT2, "l_irr_excel")


def _write_comps(wb: Any, refs: dict[str, str], payload: dict[str, Any]) -> None:
    comps = payload.get("comps")
    if not comps or comps.get("status") != "VALID":
        return
    ws = wb.create_sheet("Comps")
    ws["A1"] = "TRADING COMPARABLES"
    ws["A1"].font = TITLE
    ws["A2"] = comps.get("methodology", "")
    ws["A2"].font = NOTE
    headers = ["Ticker", "Company", "Country", "Market cap (USD)", "EV / Revenue", "EV / EBITDA", "P / E", "P / B"]
    for c, text in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=c, value=text)
        cell.font, cell.fill = WHITE_BOLD, HEADER_FILL
        ws.column_dimensions[get_column_letter(c)].width = 18 if c != 2 else 34
    peers = comps["peers"]
    for k, peer in enumerate(peers):
        row = 5 + k
        values = [peer["ticker"], peer["company_name"], peer["country"], peer.get("market_cap_usd"),
                  peer.get("ev_revenue"), peer.get("ev_ebitda"), peer.get("pe"), peer.get("pb")]
        for c, value in enumerate(values, start=1):
            cell = ws.cell(row=row, column=c, value=value)
            cell.number_format = '"$"#,##0' if c == 4 else MULT if c >= 5 else "General"
    first, last_row = 5, 4 + len(peers)
    stats_row = last_row + 2
    for k, (label, fn) in enumerate([("Median", "MEDIAN({r})"), ("25th percentile", "QUARTILE({r},1)"), ("75th percentile", "QUARTILE({r},3)")]):
        row = stats_row + k
        ws.cell(row=row, column=1, value=label).font = BOLD
        for c in range(5, 9):
            letter = get_column_letter(c)
            ws.cell(row=row, column=c, value="=IFERROR(" + fn.format(r=f"{letter}{first}:{letter}{last_row}") + ',"n/a")').number_format = MULT
    ws.cell(row=stats_row + 4, column=1, value="Medians use all listed peers; the ValuEngine engine additionally excludes out-of-range multiples.").font = NOTE


def _write_checks(wb: Any, refs: dict[str, str], payload: dict[str, Any]) -> None:
    w = SheetWriter(wb.create_sheet("Checks"), refs)
    w.ws.column_dimensions["C"].width = 22
    w.ws.column_dimensions["D"].width = 12
    w.title("MODEL CHECKS", "Workbook formulas vs. the ValuEngine Python engine (must agree within 0.0001%).")
    header = w.row
    for c, text in enumerate(["Check", "Excel result", "Python result", "Status"], start=1):
        cell = w.ws.cell(row=header, column=c, value=text)
        cell.font, cell.fill = WHITE_BOLD, HEADER_FILL
    w.row += 1
    checks: list[tuple[str, str, float | None]] = []
    intrinsic = payload.get("intrinsic_result") or {}
    if "dcf_price" in refs and intrinsic.get("implied_share_price") is not None:
        checks.append(("Implied share price", refs["dcf_price"], intrinsic["implied_share_price"]))
        checks.append(("Equity value", refs["equity"], intrinsic.get("equity_value")))
    if payload.get("mna") and "accretion" in refs:
        checks.append(("EPS accretion / dilution (year 1)", refs["accretion"], payload["mna"]["result"].get("eps_change_pct")))
        checks.append(("Break-even synergies", refs["break_even"], payload["mna"]["result"].get("break_even_pre_tax_synergy")))
    if payload.get("lbo") and "l_irr" in refs:
        checks.append(("LBO IRR", refs["l_irr"], payload["lbo"]["result"].get("irr")))
        checks.append(("LBO exit equity", refs["l_exit_eq"], payload["lbo"]["result"].get("exit_equity")))
    for label, excel_ref, python_value in checks:
        row = w.row
        w.ws.cell(row=row, column=1, value=label)
        w.ws.cell(row=row, column=2, value=f"={excel_ref}").number_format = "#,##0.0000"
        w.ws.cell(row=row, column=3, value=python_value).number_format = "#,##0.0000"
        w.ws.cell(row=row, column=4, value=f'=IF(ABS(B{row}-C{row})<=MAX(1E-6*ABS(C{row}),1E-9),"PASS","CHECK")')
        w.row += 1
    w.skip()
    w.section("Data-quality findings", width=4)
    for issue in payload.get("data_issues") or []:
        w.ws.cell(row=w.row, column=1, value=issue["severity"])
        w.ws.cell(row=w.row, column=2, value=issue["message"])
        w.row += 1


def _write_cover(ws: Any, refs: dict[str, str], payload: dict[str, Any]) -> None:
    company, currency = payload["company"], payload["currency"]
    ws.title = "Cover"
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 26
    ws["A1"] = f"ValuEngine model: {company.get('company_name')} ({company.get('ticker')})"
    ws["A1"].font = TITLE
    prov = company.get("provenance") or {}
    rows = [
        ("Currency", currency, None),
        ("Fiscal period", f"FY ending {company.get('period') or 'n/a'}", None),
        ("Data source", f"{prov.get('source_type', 'LOCAL')} (origin: {prov.get('origin', 'n/a')}, retrieved {company.get('retrieved_at') or 'n/a'})", None),
        ("Exported", payload.get("exported_at"), None),
        ("Market price", f"={refs['price']}", money_format(currency, 2)),
    ]
    if "dcf_price" in refs:
        rows += [("Intrinsic value per share", f"={refs['dcf_price']}", money_format(currency, 2)),
                 ("Upside / (downside)", f"={refs['dcf_upside']}", PCT)]
    if "accretion" in refs:
        rows.append(("M&A EPS accretion / (dilution), year 1", f"={refs['accretion']}", PCT2))
    if "l_irr" in refs:
        rows += [("LBO IRR", f"={refs['l_irr']}", PCT2), ("LBO MOIC", f"={refs['l_moic']}", MULT)]
    for k, (label, value, fmt) in enumerate(rows, start=3):
        ws.cell(row=k, column=1, value=label).font = BOLD
        cell = ws.cell(row=k, column=2, value=value)
        cell.alignment = Alignment(horizontal="left")
        if fmt:
            cell.number_format = fmt
    ws.cell(row=len(rows) + 5, column=1, value="Blue = input, black = formula. Every model sheet recalculates from the Assumptions sheet.").font = NOTE


def build_workbook(payload: dict[str, Any]) -> bytes:
    """Build the workbook and return its bytes (nothing is written to disk)."""
    wb = openpyxl.Workbook()
    refs: dict[str, str] = {}
    cover = wb.active
    _write_assumptions(wb, refs, payload)
    if payload.get("dcf"):
        _write_dcf(wb, refs, payload)
    elif payload.get("excess_return"):
        _write_excess_return(wb, refs, payload)
    _write_sensitivity(wb, payload)
    if payload.get("mna"):
        _write_accretion(wb, refs, payload)
    if payload.get("lbo"):
        _write_lbo(wb, refs, payload)
    _write_comps(wb, refs, payload)
    _write_checks(wb, refs, payload)
    _write_cover(cover, refs, payload)
    for ws in wb.worksheets:
        ws.sheet_view.showGridLines = False
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
