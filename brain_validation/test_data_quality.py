import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "mna_lbo_engine" / "modules" / "data_quality_engine.py"

spec = importlib.util.spec_from_file_location("dq", FILE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

good = {
    "revenue": 100,
    "ebitda": 25,
    "ebit": 20,
    "net_income": 15,
    "total_debt": 30,
    "cash_and_equivalents": 20,
    "shares_outstanding": 10,
    "current_price": 10,
    "market_cap": 100
}

issues = m.run_data_quality_checks(good)

print("GOOD DATA ISSUES:", issues)
assert len(issues) == 0

bad = good.copy()
bad["revenue"] = -100

issues = m.run_data_quality_checks(bad)

print("\nBAD DATA ISSUES:")
for issue in issues:
    print(issue)

assert any(i["severity"] == "HARD ERROR" for i in issues)

print("\nDATA QUALITY TEST: PASS")
