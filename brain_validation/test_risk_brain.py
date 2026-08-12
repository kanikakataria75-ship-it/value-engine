import sys
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "mna_lbo_engine" / "modules" / "risk_engine.py"

spec = importlib.util.spec_from_file_location("risk_engine", FILE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# Simple deterministic DCF stub for testing Monte Carlo brain
def fake_dcf(**kwargs):
    r = kwargs["revenue_growth_rate"]
    margin = kwargs["ebitda_margin"]
    wacc = kwargs["wacc"]

    price = 100 * (1 + r) * margin / wacc

    return {
        "status": "VALID",
        "implied_share_price": price
    }

financials = {"revenue": 100}

result = m.run_dcf_monte_carlo(
    dcf_func=fake_dcf,
    financials=financials,
    base_rev_growth=0.10,
    base_ebitda_margin=0.25,
    base_wacc=0.10,
    base_term_growth=0.03,
    tax_rate=0.25,
    mid_year_convention=False,
    iterations=1000
)

print("STATUS:", result["status"])

if result["status"] == "VALID":
    print("P10:", result["p10"])
    print("P25:", result["p25"])
    print("MEDIAN:", result["median"])
    print("P75:", result["p75"])
    print("P90:", result["p90"])
    print("DISTRIBUTION SIZE:", len(result["distribution"]))

    assert len(result["distribution"]) == 1000
    assert result["p10"] <= result["p25"] <= result["median"] <= result["p75"] <= result["p90"]

    print("RISK MONTE CARLO TEST: PASS")
