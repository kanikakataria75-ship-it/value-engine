import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from mna_lbo_engine.modules.dcf_engine import run_dcf

path = PROJECT_ROOT / "brain_validation" / "golden_data" / "aapl_real.json"
case = json.loads(path.read_text())

f = case["financials"]

financials = {
    "ticker": "AAPL",
    "company_name": "Apple Inc.",
    "revenue": f["revenue"],
    "capex": f["capex"],
    "d_and_a": f["da"],
    "total_debt": f["total_debt"],
    "cash_and_equivalents": f["cash_and_equivalents"],
    "shares_outstanding": f["shares_outstanding"],
    "current_price": f["current_price"],
    "ebit": f["ebit"],
    "book_equity": f["book_equity"],
}

result = run_dcf(
    financials=financials,
    revenue_growth_rate=0.08,
    ebitda_margin=f["ebitda"] / f["revenue"],
    wacc=0.09,
    terminal_growth_rate=0.03,
    projection_years=5,
    tax_rate=0.24,
    mid_year_convention=False,
)

print("STATUS:", result["status"])

if result["status"] == "VALID":
    print("\nAAPL DCF OUTPUT")
    print("Enterprise Value:", result["enterprise_value"])
    print("Net Debt:", result["net_debt"])
    print("Equity Value:", result["equity_value"])
    print("Implied Share Price:", result["implied_share_price"])
    print("Current Price:", result["current_price"])
    print("Upside/Downside %:", result["upside_downside_pct"])
    print("\nPROJECTIONS")
    print(result["projections_df"].to_string(index=False))
else:
    print("ERROR:", result["message"])
