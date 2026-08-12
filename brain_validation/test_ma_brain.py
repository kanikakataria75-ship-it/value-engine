import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from mna_lbo_engine.modules.ma_engine import run_ma_model

acquirer = {
    "ticker": "ACQ",
    "current_price": 100.0,
    "shares_outstanding": 100.0,
    "net_income": 10.0,
}

target = {
    "ticker": "TGT",
    "current_price": 50.0,
    "shares_outstanding": 20.0,
    "net_income": 2.0,
}

result = run_ma_model(
    acquirer_data=acquirer,
    target_data=target,
    offer_premium_pct=0.20,
    pct_cash=0.50,
    pct_stock=0.50,
    debt_interest_rate=0.10,
    revenue_synergies=10.0,
    incremental_margin=0.20,
    cost_synergies=2.0,
    integration_costs=1.0,
    tax_rate=0.25,
)

print("STATUS:", result["status"])

if result["status"] == "VALID":
    for key in [
        "offer_price",
        "total_purchase_price",
        "cash_debt_portion",
        "stock_portion",
        "new_shares_issued",
        "new_debt_interest_pre_tax",
        "after_tax_interest",
        "revenue_synergy_profit",
        "pre_tax_synergies",
        "after_tax_synergies",
        "after_tax_integration",
        "combined_net_income",
        "combined_shares",
        "post_deal_eps",
        "acquirer_standalone_eps",
        "eps_change_dollar",
        "eps_change_pct",
        "is_accretive",
        "break_even_pre_tax_synergy",
    ]:
        print(f"{key}: {result[key]}")
else:
    print("MESSAGE:", result["message"])
