"""
Risk & Statistics Engine Module.
Provides Monte Carlo simulation for DCF uncertainty and M&A/LBO Stress Testing.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import sanitize_val

def run_dcf_monte_carlo(
    dcf_func,
    financials: Dict[str, Any],
    base_rev_growth: float,
    base_ebitda_margin: float,
    base_wacc: float,
    base_term_growth: float,
    tax_rate: float,
    mid_year_convention: bool,
    iterations: int = 1000
) -> Dict[str, Any]:
    """
    Runs a controlled Monte Carlo simulation on the DCF valuation.
    Samples Rev Growth, EBITDA Margin, and WACC from normal distributions.
    """
    # Define sensible standard deviations based on assumptions
    rev_std = max(0.01, base_rev_growth * 0.1)
    margin_std = max(0.01, base_ebitda_margin * 0.1)
    wacc_std = max(0.005, base_wacc * 0.05)

    np.random.seed(42) # Reproducible results
    rev_samples = np.random.normal(base_rev_growth, rev_std, iterations)
    margin_samples = np.random.normal(base_ebitda_margin, margin_std, iterations)
    wacc_samples = np.random.normal(base_wacc, wacc_std, iterations)
    
    results = []
    for i in range(iterations):
        # Clip to sensible bounds to avoid crashes
        r = float(np.clip(rev_samples[i], -0.2, 0.5))
        m = float(np.clip(margin_samples[i], 0.01, 0.8))
        w = float(np.clip(wacc_samples[i], base_term_growth + 0.001, 0.3))
        
        try:
            res = dcf_func(
                financials=financials,
                revenue_growth_rate=r,
                ebitda_margin=m,
                wacc=w,
                terminal_growth_rate=base_term_growth,
                projection_years=5,
                tax_rate=tax_rate,
                mid_year_convention=mid_year_convention
            )
            price = res.get("implied_share_price", 0.0)
            if price > 0:
                results.append(price)
        except ValueError:
            pass # Ignore invalid constraint cases

    if not results:
        return {"status": "INVALID", "message": "Simulation failed to produce valid valuations."}

    results_arr = np.array(results)
    
    return {
        "status": "VALID",
        "median": sanitize_val(np.median(results_arr)),
        "p10": sanitize_val(np.percentile(results_arr, 10)),
        "p25": sanitize_val(np.percentile(results_arr, 25)),
        "p75": sanitize_val(np.percentile(results_arr, 75)),
        "p90": sanitize_val(np.percentile(results_arr, 90)),
        "distribution": results_arr.tolist()
    }

def run_stress_test(
    lbo_func,
    target_data: Dict[str, Any],
    entry_mult: float,
    snr_pct: float,
    sub_pct: float,
    snr_rate: float,
    sub_rate: float,
    exit_mult: float,
    rev_growth: float,
    margin: float,
    tax_rate: float
) -> Dict[str, Any]:
    """
    Stress tests the LBO under adverse scenarios (Higher Rates, Lower Growth, Multiple Contraction).
    """
    scenarios = {}
    
    # Base
    base = lbo_func(
        target_data=target_data, entry_multiple=entry_mult, senior_debt_pct=snr_pct,
        sub_debt_pct=sub_pct, senior_rate=snr_rate, sub_rate=sub_rate,
        exit_multiple=exit_mult, revenue_growth=rev_growth, ebitda_margin=margin,
        projection_years=5, tax_rate=tax_rate
    )
    scenarios["Base"] = {"IRR": base.get("irr", 0), "MoIC": base.get("moic", 0)}

    # High Interest Rate (+200bps)
    hi_int = lbo_func(
        target_data=target_data, entry_multiple=entry_mult, senior_debt_pct=snr_pct,
        sub_debt_pct=sub_pct, senior_rate=snr_rate + 0.02, sub_rate=sub_rate + 0.02,
        exit_multiple=exit_mult, revenue_growth=rev_growth, ebitda_margin=margin,
        projection_years=5, tax_rate=tax_rate
    )
    scenarios["Rates +200bps"] = {"IRR": hi_int.get("irr", 0), "MoIC": hi_int.get("moic", 0)}
    
    # Low Growth (-5%)
    lo_gr = lbo_func(
        target_data=target_data, entry_multiple=entry_mult, senior_debt_pct=snr_pct,
        sub_debt_pct=sub_pct, senior_rate=snr_rate, sub_rate=sub_rate,
        exit_multiple=exit_mult, revenue_growth=max(0, rev_growth - 0.05), ebitda_margin=margin,
        projection_years=5, tax_rate=tax_rate
    )
    scenarios["Growth -5%"] = {"IRR": lo_gr.get("irr", 0), "MoIC": lo_gr.get("moic", 0)}
    
    # Exit Contraction (-2x)
    ex_con = lbo_func(
        target_data=target_data, entry_multiple=entry_mult, senior_debt_pct=snr_pct,
        sub_debt_pct=sub_pct, senior_rate=snr_rate, sub_rate=sub_rate,
        exit_multiple=max(1.0, exit_mult - 2.0), revenue_growth=rev_growth, ebitda_margin=margin,
        projection_years=5, tax_rate=tax_rate
    )
    scenarios["Exit Multiple -2x"] = {"IRR": ex_con.get("irr", 0), "MoIC": ex_con.get("moic", 0)}

    return scenarios
