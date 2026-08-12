import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from mna_lbo_engine.modules.comps_engine import run_trading_comps

target = {"ebitda":20,"total_debt":30,"cash_and_equivalents":10,"shares_outstanding":10}

peers = [
    {"company_name":"Bad Peer","market_cap":100,"total_debt":20,"cash_and_equivalents":10,
     "revenue":0,"ebitda":10,"net_income":0},
]

r = run_trading_comps(target, peers)

print("STATUS:", r["status"])
print(r["peer_multiples_df"].to_string(index=False))
