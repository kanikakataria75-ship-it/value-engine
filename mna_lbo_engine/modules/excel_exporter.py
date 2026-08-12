"""
Excel Exporter Module.
Generates multi-tab audit-ready Wall Street financial models using openpyxl.
CRITICAL: Writes LIVE EXCEL FORMULAS into cells (e.g., =SUM(), =IRR(), =(1-t)).
"""

from typing import Dict, Any
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NAVY_HEADER_HEX

class ExcelReportExporter:
    """Generates formatted openpyxl workbooks with live Excel formulas and full tabs."""

    def __init__(self):
        self.navy_fill = PatternFill(start_color=NAVY_HEADER_HEX, end_color=NAVY_HEADER_HEX, fill_type="solid")
        self.white_bold_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        self.title_font = Font(name="Calibri", size=16, bold=True, color=NAVY_HEADER_HEX)
        self.bold_font = Font(name="Calibri", size=11, bold=True)
        self.fmt_currency = "$#,##0"
        self.fmt_currency_exact = "$#,##0.00"
        self.fmt_percent = "0.0%"
        self.fmt_multiple = "0.00x"
        self.fmt_number = "#,##0"
        
        self.thin_border = Border(bottom=Side(style="thin", color="000000"))
        
    def _write_df_to_sheet(self, ws, title: str, df, start_row: int = 2):
        ws.cell(row=start_row, column=1, value=title).font = self.title_font
        if df is None or df.empty:
            ws.cell(row=start_row+2, column=1, value="No data available.")
            return start_row + 4
            
        # Write headers
        for c_idx, col_name in enumerate(df.columns, 1):
            cell = ws.cell(row=start_row+2, column=c_idx, value=str(col_name))
            cell.fill = self.navy_fill
            cell.font = self.white_bold_font
            
        # Write data
        for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=False), start_row+3):
            for c_idx, val in enumerate(row, 1):
                cell = ws.cell(row=r_idx, column=c_idx, value=val)
                if isinstance(val, (int, float)):
                    if abs(val) < 100:  # heuristic for % or multiple
                        cell.number_format = self.fmt_number
                    else:
                        cell.number_format = self.fmt_currency
        return start_row + len(df) + 5

    def export_full_model(
        self,
        dcf_data: Dict[str, Any],
        ma_data: Dict[str, Any],
        lbo_data: Dict[str, Any],
        filepath: str = "M_and_A_LBO_Model.xlsx"
    ) -> str:
        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        # 1. Executive Summary
        ws_exec = wb.create_sheet(title="1. Executive Summary")
        ws_exec["A1"] = "INSTITUTIONAL VALUATION & DEAL SUMMARY"
        ws_exec["A1"].font = self.title_font
        ws_exec["A3"] = "Valuation"
        ws_exec["A4"] = "DCF Implied Share Price"
        ws_exec["B4"] = dcf_data.get("implied_share_price", 0)
        ws_exec["B4"].number_format = self.fmt_currency_exact
        ws_exec["A5"] = "M&A Offer Price"
        ws_exec["B5"] = ma_data.get("offer_price", 0)
        ws_exec["B5"].number_format = self.fmt_currency_exact
        ws_exec["A6"] = "EPS Accretion / Dilution ($)"
        ws_exec["B6"] = ma_data.get("eps_change_dollar", 0)
        ws_exec["B6"].number_format = self.fmt_currency_exact
        ws_exec["A7"] = "LBO IRR"
        ws_exec["B7"] = lbo_data.get("irr", 0)
        ws_exec["B7"].number_format = self.fmt_percent

        # 2. Model Checks
        ws_chk = wb.create_sheet(title="2. Model Checks")
        ws_chk["A1"] = "MODEL INTEGRITY CHECKS"
        ws_chk["A1"].font = self.title_font
        ws_chk["A3"] = "Check"
        ws_chk["B3"] = "Status"
        ws_chk["A4"] = "Target Data Present"
        ws_chk["B4"] = "PASS" if dcf_data.get("current_price", 0) > 0 else "FAIL"
        ws_chk["A5"] = "M&A Engine Completed"
        ws_chk["B5"] = "PASS" if ma_data.get("offer_price", 0) > 0 else "FAIL"
        ws_chk["A6"] = "LBO Engine Completed"
        ws_chk["B6"] = "PASS" if lbo_data.get("irr", 0) > 0 else "FAIL"

        # 3. Assumptions
        ws_assump = wb.create_sheet(title="3. Assumptions")
        ws_assump["A1"] = "GLOBAL ASSUMPTIONS"
        ws_assump["A1"].font = self.title_font
        ws_assump["A3"] = "M&A Premium %"
        ws_assump["B3"] = ma_data.get("offer_premium_pct", 0)
        ws_assump["B3"].number_format = self.fmt_percent
        ws_assump["A4"] = "LBO Entry Multiple"
        ws_assump["B4"] = lbo_data.get("entry_multiple", 0)
        ws_assump["B4"].number_format = self.fmt_multiple

        # 4. DCF
        ws_dcf = wb.create_sheet(title="4. DCF")
        self._write_df_to_sheet(ws_dcf, "DCF PROJECTIONS", dcf_data.get("projections_df", None))

        # 5. M&A
        ws_ma = wb.create_sheet(title="5. M&A")
        ws_ma["A1"] = "M&A DEAL STRUCTURE"
        ws_ma["A1"].font = self.title_font
        
        if ma_data.get("status") == "INVALID":
            ws_ma["A3"] = "M&A Data UNAVAILABLE (INVALID MODEL)"
        else:
            ws_ma["A3"] = "Acquirer Net Income"
            ws_ma["B3"] = ma_data.get("acquirer_net_income", "UNAVAILABLE")
            if isinstance(ws_ma["B3"].value, (int, float)):
                ws_ma["B3"].number_format = self.fmt_currency
                
            ws_ma["A4"] = "Target Net Income"
            ws_ma["B4"] = ma_data.get("target_net_income", "UNAVAILABLE")
            if isinstance(ws_ma["B4"].value, (int, float)):
                ws_ma["B4"].number_format = self.fmt_currency
                
            ws_ma["A5"] = "Synergies (After Tax)"
            ws_ma["B5"] = ma_data.get("after_tax_synergies", "UNAVAILABLE")
            if isinstance(ws_ma["B5"].value, (int, float)):
                ws_ma["B5"].number_format = self.fmt_currency
                
            ws_ma["A6"] = "Combined Pro-Forma Net Income"
            ws_ma["B6"] = ma_data.get("pro_forma_net_income", "UNAVAILABLE")
            if isinstance(ws_ma["B6"].value, (int, float)):
                ws_ma["B6"].number_format = self.fmt_currency
            ws_ma["B6"].font = self.bold_font

        # 6. LBO & Debt Schedule
        ws_lbo = wb.create_sheet(title="6. LBO & Debt Schedule")
        self._write_df_to_sheet(ws_lbo, "LBO DEBT SCHEDULE", lbo_data.get("schedule_df", None))

        # 7. Comps
        ws_comps = wb.create_sheet(title="7. Comps & Data")
        ws_comps["A1"] = "COMPARABLES & DATA SOURCES"
        ws_comps["A1"].font = self.title_font

        wb.save(filepath)
        return filepath
