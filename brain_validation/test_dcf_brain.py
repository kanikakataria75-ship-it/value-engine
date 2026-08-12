import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from mna_lbo_engine.modules.dcf_engine import run_dcf

path = PROJECT_ROOT / "brain_validation" / "golden_data" / "testco_dcf.json"
case = json.loads(path.read_text())

f = case["financials"]
v = case["valuation"]
c = case["capital_structure"]

financials = {
    "ticker": case["company"],
    "company_name": "Test Company",
    "revenue": f["revenue"],
    "capex": f["capex"],
    "d_and_a": f["da"],
    "total_debt": c["debt"],
    "cash_and_equivalents": c["cash"],
    "shares_outstanding": c["shares_outstanding"],
    "current_price": 10.0,
    "ebit": f["revenue"] * f["ebitda_margin"] - f["da"],
    "book_equity": 50.0,
}

result = run_dcf(
    financials=financials,
    revenue_growth_rate=f["revenue_growth"],
    ebitda_margin=f["ebitda_margin"],
    wacc=v["wacc"],
    terminal_growth_rate=v["terminal_growth"],
    projection_years=v["forecast_years"],
    tax_rate=f["tax_rate"],
    mid_year_convention=False,
)

print("STATUS:", result["status"])

if result["status"] == "VALID":
    print("\nDCF OUTPUT")
    print("Enterprise Value:", result["enterprise_value"])
    print("Net Debt:", result["net_debt"])
    print("Equity Value:", result["equity_value"])
    print("Implied Share Price:", result["implied_share_price"])

    print("\nPROJECTIONS")
    print(result["projections_df"].to_string(index=False))
else:
    print("ERROR:", result["message"])
