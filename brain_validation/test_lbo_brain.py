import sys
from pathlib import Path
import importlib.util

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LBO_FILE = PROJECT_ROOT / "mna_lbo_engine" / "modules" / "lbo_engine.py"

spec = importlib.util.spec_from_file_location("lbo_engine", LBO_FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

run_lbo_model = module.run_lbo_model

target = {
    "ticker": "TESTCO",
    "revenue": 100.0,
    "ebitda": 25.0,
    "capex": 5.0,
    "d_and_a": 5.0,
}

result = run_lbo_model(
    target_data=target,
    entry_multiple=8.0,
    senior_debt_pct=0.50,
    sub_debt_pct=0.20,
    senior_rate=0.08,
    sub_rate=0.12,
    exit_multiple=8.0,
    revenue_growth=0.10,
    ebitda_margin=0.25,
    projection_years=5,
    tax_rate=0.25,
)

print("STATUS:", result["status"])

if result["status"] == "VALID":
    print("\nLBO OUTPUT")
    print("Entry EV:", result["entry_ev"])
    print("Initial Debt:", result["total_debt_initial"])
    print("Sponsor Equity:", result["sponsor_initial_equity"])
    print("Exit EBITDA:", result["exit_ebitda"])
    print("Exit EV:", result["exit_ev"])
    print("Exit Debt:", result["exit_debt"])
    print("Exit Equity:", result["exit_equity"])
    print("MoIC:", result["moic"])
    print("IRR:", result["irr"])

    print("\nDEBT SCHEDULE")
    print(result["schedule_df"].to_string(index=False))
else:
    print("MESSAGE:", result["message"])
