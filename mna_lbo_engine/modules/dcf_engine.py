"""
DCF Valuation Engine Module.
Computes CAPM Cost of Equity, WACC, 5-Year Unlevered Free Cash Flow (UFCF) projections,
Gordon Growth Terminal Value, Enterprise Value, Equity Value, and Implied Intrinsic Share Price.
"""

from typing import Dict, Any
import pandas as pd
import numpy as np
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    RISK_FREE_RATE,
    MARKET_RISK_PREMIUM,
    CORPORATE_TAX_RATE,
    DEFAULT_COST_OF_DEBT,
    TERMINAL_GROWTH_RATE,
)

def run_dcf(
    financials: Dict[str, Any],
    revenue_growth_rate: float,
    ebitda_margin: float,
    wacc: float,
    terminal_growth_rate: float,
    projection_years: int = 5,
    tax_rate: float = CORPORATE_TAX_RATE,
    mid_year_convention: bool = False,
) -> Dict[str, Any]:
    """
    Run 5-Year Unlevered Free Cash Flow (UFCF) DCF model with Gordon Growth safeguards.
    """
    # CRITICAL: Do not invent missing data.
    base_revenue = financials.get("revenue")
    base_capex = financials.get("capex")
    base_da = financials.get("d_and_a")
    
    if base_revenue is None:
        return {"status": "INVALID", "message": "Missing Revenue in source data."}
    if base_revenue <= 0:
        return {"status": "INVALID", "message": "Non-positive Revenue is invalid for standard DCF."}
        
    if base_capex is None:
        return {"status": "INVALID", "message": "Missing CapEx in source data."}
    if base_da is None:
        return {"status": "INVALID", "message": "Missing D&A in source data."}
        
    # CRITICAL GUARD: Ensure WACC > terminal_growth
    if wacc <= terminal_growth_rate:
        return {
            "status": "INVALID", 
            "message": f"Invalid valuation assumption: Terminal Growth ({terminal_growth_rate*100:.2f}%) must be strictly below WACC ({wacc*100:.2f}%)."
        }

    # Historical percentages for forecasting
    capex_pct_rev = base_capex / base_revenue
    da_pct_rev = base_da / base_revenue
    nwc_pct_inc_rev = 0.02 # Assuming standard working capital assumption

    projections = []
    current_rev = base_revenue
    pv_ufcf_sum = 0.0

    for year in range(1, projection_years + 1):
        prev_rev = current_rev
        current_rev = prev_rev * (1.0 + revenue_growth_rate)
        inc_rev = current_rev - prev_rev

        ebitda = current_rev * ebitda_margin
        da = current_rev * da_pct_rev
        ebit = ebitda - da

        taxes = max(0.0, ebit * tax_rate)
        ebat = ebit - taxes

        capex = current_rev * capex_pct_rev
        delta_nwc = inc_rev * nwc_pct_inc_rev

        # UFCF = EBIT*(1-t) + D&A - CapEx - Delta NWC
        ufcf = ebat + da - capex - delta_nwc

        t_discount = year - 0.5 if mid_year_convention else float(year)
        discount_factor = 1.0 / ((1.0 + wacc) ** t_discount)
        pv_ufcf = ufcf * discount_factor
        pv_ufcf_sum += pv_ufcf

        projections.append({
            "Year": year,
            "Revenue": current_rev,
            "Revenue Growth": revenue_growth_rate,
            "EBITDA": ebitda,
            "EBITDA Margin": ebitda_margin,
            "D&A": da,
            "EBIT": ebit,
            "Taxes": taxes,
            "EBIT(1-t)": ebat,
            "CapEx": capex,
            "Delta NWC": delta_nwc,
            "UFCF": ufcf,
            "Discount Factor": discount_factor,
            "PV of UFCF": pv_ufcf,
        })

    last_ufcf = projections[-1]["UFCF"]
    denom = wacc - terminal_growth_rate
    terminal_value = (last_ufcf * (1.0 + terminal_growth_rate)) / denom
    
    tv_discount_time = (projection_years - 0.5) if mid_year_convention else float(projection_years)
    discount_denom = (1.0 + wacc) ** tv_discount_time
    pv_terminal_value = terminal_value / discount_denom if discount_denom != 0 else 0.0

    # Valuation Summary
    enterprise_value = pv_ufcf_sum + pv_terminal_value
    
    total_debt = financials.get("total_debt")
    cash_and_eq = financials.get("cash_and_equivalents")
    
    if total_debt is None or cash_and_eq is None:
        return {"status": "INVALID", "message": "Missing Debt or Cash balances to bridge EV to Equity Value."}
        
    total_debt = float(total_debt)
    cash_and_eq = float(cash_and_eq)
    
    if total_debt < 0 or cash_and_eq < 0:
        return {"status": "INVALID", "message": "Debt and Cash balances cannot be negative."}
        
    net_debt = total_debt - cash_and_eq
    
    equity_value = enterprise_value - net_debt
    shares_outstanding = financials.get("shares_outstanding")
    
    if shares_outstanding is None or shares_outstanding <= 0:
        return {"status": "INVALID", "message": "Missing or non-positive shares outstanding."}
        
    implied_share_price = equity_value / shares_outstanding

    current_price = financials.get("current_price", 0.0)
    upside_downside_pct = ((implied_share_price / current_price) - 1.0) * 100.0 if current_price > 0 else 0.0

    # ROIC Diagnostic
    base_ebit = financials.get("ebit", 0.0)
    nopat = base_ebit * (1.0 - tax_rate)
    book_equity = financials.get("book_equity", 0.0)
    invested_capital = total_debt + book_equity - cash_and_eq
    roic = (nopat / invested_capital) if invested_capital > 0 else 0.0
    value_creation_spread = roic - wacc

    return {
        "status": "VALID",
        "ticker": financials.get("ticker", "TICKER"),
        "company_name": financials.get("company_name", "Company"),
        "wacc": wacc,
        "terminal_growth_rate": terminal_growth_rate,
        "pv_ufcf_sum": pv_ufcf_sum,
        "terminal_value": terminal_value,
        "pv_terminal_value": pv_terminal_value,
        "enterprise_value": enterprise_value,
        "net_debt": net_debt,
        "equity_value": equity_value,
        "implied_share_price": implied_share_price,
        "current_price": current_price,
        "upside_downside_pct": upside_downside_pct,
        "shares_outstanding": shares_outstanding,
        "roic": roic,
        "value_creation_spread": value_creation_spread,
        "mid_year_convention": mid_year_convention,
        "projections_df": pd.DataFrame(projections),
    }
