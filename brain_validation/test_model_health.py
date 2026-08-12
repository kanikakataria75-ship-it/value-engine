import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "mna_lbo_engine" / "modules" / "model_health.py"

spec = importlib.util.spec_from_file_location("health", FILE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

dcf = {
    "status": "VALID",
    "terminal_value": 100,
    "value_creation_spread": 0.05,
    "current_price": 10,
    "implied_share_price": 15
}

ma = {
    "status": "VALID",
    "is_accretive": True,
    "break_even_pre_tax_synergy": 0,
    "pre_tax_synergies": 10
}

lbo = {
    "status": "VALID",
    "sponsor_initial_equity": 100,
    "irr": 0.25
}

result = m.evaluate_model_health(
    dcf_res=dcf,
    ma_res=ma,
    lbo_res=lbo,
    data_quality_issues=[]
)

print("MODEL HEALTH:", str(result).encode("ascii", "ignore").decode("ascii"))

assert "VALID" in result["status"]

score = m.calculate_deal_quality(
    dcf_res=dcf,
    ma_res=ma,
    lbo_res=lbo,
    comps_res={"status": "VALID"}
)

print("\nDEAL QUALITY:", str(score).encode("ascii", "ignore").decode("ascii"))

assert score["score"] == 100.0

print("\nMODEL HEALTH TEST: PASS")
