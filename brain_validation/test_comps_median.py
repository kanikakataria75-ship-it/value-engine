import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from mna_lbo_engine.modules.comps_engine import run_trading_comps

target = {
    "ebitda":20,
    "total_debt":30,
    "cash_and_equivalents":10,
    "shares_outstanding":10
}

peers = [
    {"company_name":"Low","market_cap":100,"total_debt":0,"cash_and_equivalents":0,
     "revenue":50,"ebitda":10,"net_income":5},

    {"company_name":"Mid","market_cap":200,"total_debt":0,"cash_and_equivalents":0,
     "revenue":50,"ebitda":10,"net_income":5},

    {"company_name":"High","market_cap":300,"total_debt":0,"cash_and_equivalents":0,
     "revenue":50,"ebitda":10,"net_income":5},
]

r = run_trading_comps(target, peers)

print("STATUS:", r["status"])
print("\nPEERS:")
print(r["peer_multiples_df"].to_string(index=False))

print("\nDISTRIBUTION:")
print(r["distribution_df"].to_string())

print("\nIMPLIED SHARE PRICE:", r["implied_share_price_median"])
