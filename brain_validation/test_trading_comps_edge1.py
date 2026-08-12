import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from mna_lbo_engine.modules.comps_engine import run_trading_comps

target = {
    "ticker": "TESTCO",
    "ebitda": 20.0,
    "total_debt": 30.0,
    "cash_and_equivalents": 10.0,
    "shares_outstanding": 10.0,
}

result = run_trading_comps(target, [])

print("STATUS:", result["status"])
print("MESSAGE:", result.get("message"))
print("IMPLIED PRICE:", result.get("implied_share_price_median"))
