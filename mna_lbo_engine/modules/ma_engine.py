"""
M&A Accretion/Dilution Engine Module.
Simulates Cash vs Stock financing mechanics, Purchase Price calculation, New Debt interest,
Revenue & Cost synergies, Integration costs, Pro-Forma Net Income & Share Count, 
EPS Accretion/Dilution metrics, and Break-Even Analysis.
"""

from typing import Dict, Any
import pandas as pd
import numpy as np
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CORPORATE_TAX_RATE, SENIOR_DEBT_INTEREST

def run_ma_model(
    acquirer_data: Dict[str, Any],
    target_data: Dict[str, Any],
    offer_premium_pct: float,
    pct_cash: float,
    pct_stock: float,
    debt_interest_rate: float,
    revenue_synergies: float,
    incremental_margin: float,
    cost_synergies: float,
    integration_costs: float,
    tax_rate: float,
) -> Dict[str, Any]:
    """
    Run M&A Accretion / Dilution deal model.
    Returns structured INVALID if inputs are missing.
    """
    acquirer_price = acquirer_data.get("current_price")
    acquirer_shares = acquirer_data.get("shares_outstanding")
    acquirer_net_income = acquirer_data.get("net_income")
    
    target_price = target_data.get("current_price")
    target_shares = target_data.get("shares_outstanding")
    target_net_income = target_data.get("net_income")
    
    if None in [acquirer_price, acquirer_shares, acquirer_net_income, target_price, target_shares, target_net_income]:
        return {"status": "INVALID", "message": "Missing critical financial data for Acquirer or Target."}
        
    if acquirer_shares <= 0 or acquirer_price <= 0:
        return {"status": "INVALID", "message": "Acquirer shares or price must be positive."}

    if not np.isclose(pct_cash + pct_stock, 1.0, atol=1e-5):
        return {"status": "INVALID", "message": "Cash consideration + stock consideration must equal 100%."}

    offer_price = target_price * (1.0 + offer_premium_pct)
    total_purchase_price = offer_price * target_shares

    cash_debt_portion = total_purchase_price * pct_cash
    stock_portion = total_purchase_price * pct_stock

    new_shares_issued = stock_portion / acquirer_price
    new_debt_annual_interest = cash_debt_portion * debt_interest_rate
    after_tax_interest = new_debt_annual_interest * (1.0 - tax_rate)

    # Revenue Synergies mapped to profit via Incremental Margin
    revenue_synergy_profit = revenue_synergies * incremental_margin
    pre_tax_synergies = revenue_synergy_profit + cost_synergies
    after_tax_synergies = pre_tax_synergies * (1.0 - tax_rate)

    # Integration Costs (One-time, subtracted from Year 1 Pro Forma)
    after_tax_integration = integration_costs * (1.0 - tax_rate)

    combined_net_income = acquirer_net_income + target_net_income + after_tax_synergies - after_tax_interest - after_tax_integration
    combined_shares = acquirer_shares + new_shares_issued
    
    post_deal_eps = combined_net_income / combined_shares
    acquirer_eps = acquirer_net_income / acquirer_shares

    eps_change_dollar = post_deal_eps - acquirer_eps
    eps_change_pct = (eps_change_dollar / abs(acquirer_eps)) * 100.0 if acquirer_eps != 0 else 0.0

    is_accretive = eps_change_dollar >= 0

    # Break-Even Analysis
    target_ni_needed = acquirer_eps * combined_shares
    shortfall = target_ni_needed - acquirer_net_income - target_net_income + after_tax_interest + after_tax_integration
    
    if shortfall <= 0:
        break_even_pre_tax_synergy = 0.0
    else:
        break_even_pre_tax_synergy = shortfall / (1.0 - tax_rate) if tax_rate < 1 else 0.0

    return {
        "status": "VALID",
        "acquirer_ticker": acquirer_data.get("ticker", "ACQ"),
        "target_ticker": target_data.get("ticker", "TGT"),
        "offer_price": offer_price,
        "total_purchase_price": total_purchase_price,
        "cash_debt_portion": cash_debt_portion,
        "stock_portion": stock_portion,
        "new_shares_issued": new_shares_issued,
        "new_debt_interest_pre_tax": new_debt_annual_interest,
        "after_tax_interest": after_tax_interest,
        "revenue_synergy_profit": revenue_synergy_profit,
        "pre_tax_synergies": pre_tax_synergies,
        "after_tax_synergies": after_tax_synergies,
        "after_tax_integration": after_tax_integration,
        "combined_net_income": combined_net_income,
        "combined_shares": combined_shares,
        "post_deal_eps": post_deal_eps,
        "acquirer_standalone_eps": acquirer_eps,
        "eps_change_dollar": eps_change_dollar,
        "eps_change_pct": eps_change_pct,
        "is_accretive": is_accretive,
        "break_even_pre_tax_synergy": break_even_pre_tax_synergy
    }
