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
    "shares_outstanding": 10.0,
    "current_price": 10.0,
    "ebit": 20.0,
    "book_equity": 50.0,
}

result = run_dcf(
    financials=financials,
    revenue_growth_rate=0.10,
    ebitda_margin=0.25,
    wacc=0.03,
    terminal_growth_rate=0.03,
    projection_years=5,
    tax_rate=0.25,
)

print("STATUS:", result["status"])
print("MESSAGE:", result.get("message"))
