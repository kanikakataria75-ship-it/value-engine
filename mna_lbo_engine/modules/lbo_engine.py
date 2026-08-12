"""
LBO Returns & Waterfall Engine Module.
Simulates LBO Sources & Uses, 5-Year Debt Waterfall (Mandatory Paydowns & Cash Sweep),
and calculates IRR, MoIC, and Returns Attribution (Value Creation Bridge).
"""

from typing import Dict, Any
import numpy as np
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CORPORATE_TAX_RATE, SENIOR_DEBT_INTEREST

def run_lbo_model(
    target_data: Dict[str, Any],
    entry_multiple: float,
    senior_debt_pct: float,
    sub_debt_pct: float,
    senior_rate: float,
    sub_rate: float,
    exit_multiple: float,
    revenue_growth: float,
    ebitda_margin: float,
    projection_years: int = 5,
    tax_rate: float = CORPORATE_TAX_RATE,
) -> Dict[str, Any]:
    """
    Run institutional LBO Returns and Debt Waterfall model.
    """
    base_revenue = target_data.get("revenue")
    base_ebitda = target_data.get("ebitda")
    
    if base_revenue is None or base_ebitda is None or base_ebitda <= 0:
        return {"status": "INVALID", "message": "Missing or non-positive historical EBITDA."}

    # CRITICAL: Validate Capital Structure
    if senior_debt_pct + sub_debt_pct > 1.0:
        return {"status": "INVALID", "message": "Total Debt % cannot exceed 100% of Entry EV."}

    entry_ev = base_ebitda * entry_multiple
    snr_debt_initial = entry_ev * senior_debt_pct
    sub_debt_initial = entry_ev * sub_debt_pct
    total_debt_initial = snr_debt_initial + sub_debt_initial
    
    sponsor_initial_equity = entry_ev - total_debt_initial
    
    # CRITICAL: Sponsor equity must be strictly positive
    if sponsor_initial_equity <= 0:
        return {"status": "INVALID", "message": f"Negative or zero Sponsor Equity (${sponsor_initial_equity/1e9:.2f}B). Deal structure is invalid."}

    # Operating Assumptions
    base_capex = target_data.get("capex", base_revenue * 0.04)
    base_da = target_data.get("d_and_a", base_revenue * 0.035)
    capex_pct_rev = base_capex / base_revenue
    da_pct_rev = base_da / base_revenue
    nwc_pct_inc_rev = 0.02
    
    # Mandatory paydown assumption
    snr_mandatory_pct = 0.01 

    current_rev = base_revenue
    snr_balance = snr_debt_initial
    sub_balance = sub_debt_initial
    
    schedule = []
    
    for year in range(1, projection_years + 1):
        prev_rev = current_rev
        current_rev = prev_rev * (1.0 + revenue_growth)
        inc_rev = current_rev - prev_rev
        
        ebitda = current_rev * ebitda_margin
        da = current_rev * da_pct_rev
        ebit = ebitda - da
        
        # Interest based on beginning balance
        snr_interest = snr_balance * senior_rate
        sub_interest = sub_balance * sub_rate
        total_interest = snr_interest + sub_interest
        
        ebt = ebit - total_interest
        taxes = max(0.0, ebt * tax_rate)
        
        capex = current_rev * capex_pct_rev
        delta_nwc = inc_rev * nwc_pct_inc_rev
        
        # Cash Available for Debt Service (CADS) = EBITDA - Interest - Taxes - CapEx - deltaNWC
        cads = ebitda - total_interest - taxes - capex - delta_nwc
        
        # Debt Paydown Waterfall
        snr_mandatory_paydown = 0.0
        snr_sweep = 0.0
        sub_sweep = 0.0
        
        if cads > 0:
            # We can only make mandatory payments if we have CADS (no revolver modeled)
            snr_mandatory_paydown = min(snr_balance, snr_debt_initial * snr_mandatory_pct)
            snr_mandatory_paydown = min(snr_mandatory_paydown, cads)
            
            cads_after_mandatory = cads - snr_mandatory_paydown
            if cads_after_mandatory > 0:
                snr_sweep = min(snr_balance - snr_mandatory_paydown, cads_after_mandatory)
                cads_after_snr = cads_after_mandatory - snr_sweep
                
                if cads_after_snr > 0:
                    sub_sweep = min(sub_balance, cads_after_snr)
        
        snr_total_paydown = snr_mandatory_paydown + snr_sweep
        
        # End balances
        snr_balance_end = max(0.0, snr_balance - snr_total_paydown)
        sub_balance_end = max(0.0, sub_balance - sub_sweep)
        
        schedule.append({
            "Year": year,
            "Revenue": current_rev,
            "EBITDA": ebitda,
            "CADS": cads,
            "Beg. Senior Debt": snr_balance,
            "Senior Interest": snr_interest,
            "Senior Paydown": snr_total_paydown,
            "End Senior Debt": snr_balance_end,
            "Beg. Sub Debt": sub_balance,
            "Sub Interest": sub_interest,
            "Sub Paydown": sub_sweep,
            "End Sub Debt": sub_balance_end,
            "Total End Debt": snr_balance_end + sub_balance_end
        })
        
        snr_balance = snr_balance_end
        sub_balance = sub_balance_end

    # Exit Math
    exit_ebitda = schedule[-1]["EBITDA"]
    exit_ev = exit_ebitda * exit_multiple
    exit_debt = schedule[-1]["Total End Debt"]
    exit_equity = max(0.0, exit_ev - exit_debt)
    
    # Returns
    moic = exit_equity / sponsor_initial_equity if sponsor_initial_equity > 0 else 0.0
    
    # IRR Cashflows: 1 outflow at t=0, 1 inflow at t=5. This is conventional.
    # Therefore, CAGR = IRR mathematically.
    if moic > 0:
        irr = (moic ** (1.0 / projection_years)) - 1.0
    else:
        irr = -1.0 # 100% loss
        
    # Returns Attribution
    # Total Value Creation = Exit Equity - Initial Equity
    total_value_creation = exit_equity - sponsor_initial_equity
    
    # 1. EBITDA Growth: (Exit EBITDA - Entry EBITDA) * Entry Multiple
    attr_ebitda_growth = (exit_ebitda - base_ebitda) * entry_multiple
    
    # 2. Multiple Expansion: Exit EBITDA * (Exit Multiple - Entry Multiple)
    attr_multiple_expansion = exit_ebitda * (exit_multiple - entry_multiple)
    
    # 3. Debt Paydown: Initial Debt - Exit Debt
    attr_debt_paydown = total_debt_initial - exit_debt
    
    # The remainder is cash generation / other effects
    # Since we assume 0 cash accumulation (all CADS swept to debt), attr_cash_generation = 0
    attr_cash_generation = total_value_creation - (attr_ebitda_growth + attr_multiple_expansion + attr_debt_paydown)

    return {
        "status": "VALID",
        "entry_ev": entry_ev,
        "total_debt_initial": total_debt_initial,
        "sponsor_initial_equity": sponsor_initial_equity,
        "exit_ebitda": exit_ebitda,
        "exit_ev": exit_ev,
        "exit_debt": exit_debt,
        "exit_equity": exit_equity,
        "moic": moic,
        "irr": irr,
        "total_value_creation": total_value_creation,
        "attr_ebitda_growth": attr_ebitda_growth,
        "attr_multiple_expansion": attr_multiple_expansion,
        "attr_debt_paydown": attr_debt_paydown,
        "attr_cash_generation": attr_cash_generation,
        "schedule_df": pd.DataFrame(schedule)
    }
