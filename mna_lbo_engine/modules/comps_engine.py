"""
Trading and Transaction Comparables Engine.
Computes institutional peer distribution (Min, 25th, Median, Mean, 75th, Max).
"""

from typing import Dict, Any, List
import pandas as pd
import numpy as np
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import sanitize_val

def _compute_multiples(peers: List[Dict[str, Any]]) -> pd.DataFrame:
    multiples = []
    for p in peers:
        mcap = sanitize_val(p.get("market_cap", 0))
        debt = max(0.0, sanitize_val(p.get("total_debt", 0)))
        cash = max(0.0, sanitize_val(p.get("cash_and_equivalents", 0)))
        ev = mcap + debt - cash
        
        rev = sanitize_val(p.get("revenue", 0))
        ebitda = sanitize_val(p.get("ebitda", 0))
        ni = sanitize_val(p.get("net_income", 0))
        
        ev_rev = ev / rev if rev > 0 else np.nan
        ev_ebitda = ev / ebitda if ebitda > 0 else np.nan
        pe = mcap / ni if ni > 0 else np.nan
        
        multiples.append({
            "Company": p.get("company_name", p.get("ticker", "Unknown")),
            "EV / Rev": ev_rev,
            "EV / EBITDA": ev_ebitda,
            "P / E": pe
        })
    return pd.DataFrame(multiples)

def run_trading_comps(target_data: Dict[str, Any], peers_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not peers_data:
        return {"status": "UNAVAILABLE", "message": "Trading Comps Data Unavailable"}
        
    df = _compute_multiples(peers_data)
    
    # Calculate distributions safely
    stats = df[["EV / Rev", "EV / EBITDA", "P / E"]].agg(['min', lambda x: x.quantile(0.25), 'median', 'mean', lambda x: x.quantile(0.75), 'max']).T
    stats.columns = ['Min', '25th', 'Median', 'Mean', '75th', 'Max']
    
    median_ev_ebitda = sanitize_val(stats.loc["EV / EBITDA", "Median"])
    target_ebitda = sanitize_val(target_data.get("ebitda", 0))
    implied_ev = target_ebitda * median_ev_ebitda if not np.isnan(median_ev_ebitda) else 0
    
    target_debt = max(0.0, sanitize_val(target_data.get("total_debt", 0)))
    target_cash = max(0.0, sanitize_val(target_data.get("cash_and_equivalents", 0)))
    implied_eq = implied_ev - target_debt + target_cash
    
    shares = sanitize_val(target_data.get("shares_outstanding", 0))
    implied_price = implied_eq / shares if shares > 0 else 0
    
    return {
        "status": "VALID",
        "implied_share_price_median": implied_price,
        "peer_multiples_df": df,
        "distribution_df": stats,
    }

def run_transaction_comps(target_data: Dict[str, Any], transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Never invent transaction comps
    if not transactions:
        return {"status": "UNAVAILABLE", "message": "TRANSACTION COMPS UNAVAILABLE"}
        
    df = _compute_multiples(transactions)
    stats = df[["EV / Rev", "EV / EBITDA", "P / E"]].agg(['min', lambda x: x.quantile(0.25), 'median', 'mean', lambda x: x.quantile(0.75), 'max']).T
    stats.columns = ['Min', '25th', 'Median', 'Mean', '75th', 'Max']
    
    median_ev_ebitda = sanitize_val(stats.loc["EV / EBITDA", "Median"])
    target_ebitda = sanitize_val(target_data.get("ebitda", 0))
    implied_ev = target_ebitda * median_ev_ebitda if not np.isnan(median_ev_ebitda) else 0
    
    target_debt = target_data.get("total_debt")
    if target_debt is None:
        return {"status": "INVALID", "message": "Target debt missing."}
    if target_debt < 0:
        return {"status": "INVALID", "message": "Target debt cannot be negative."}
        
    target_cash = target_data.get("cash_and_equivalents")
    if target_cash is None:
        return {"status": "INVALID", "message": "Target cash missing."}
    if target_cash < 0:
        return {"status": "INVALID", "message": "Target cash cannot be negative."}
        
    implied_eq = implied_ev - target_debt + target_cash
    shares = target_data.get("shares_outstanding")
    if shares is None or shares <= 0:
        return {"status": "INVALID", "message": "Shares missing or non-positive."}
        
    implied_price = implied_eq / shares
    
    return {
        "status": "VALID",
        "implied_share_price_median": implied_price,
        "transaction_multiples_df": df,
        "distribution_df": stats,
    }
