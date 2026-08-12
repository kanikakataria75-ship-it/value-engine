import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from mna_lbo_engine.modules.dcf_engine import run_dcf

financials = {
    "ticker": "TESTCO",
    "revenue": 100.0,
    "capex": 5.0,
    "d_and_a": 5.0,
    "total_debt": 30.0,
    "cash_and_equivalents": 20.0,
    "shares_outstanding": None,
    "current_price": 10.0,
    "ebit": 20.0,
    "book_equity": 50.0,
}

result = run_dcf(financials, 0.10, 0.25, 0.10, 0.03, 5, 0.25)

print("STATUS:", result["status"])
print("MESSAGE:", result.get("message"))
