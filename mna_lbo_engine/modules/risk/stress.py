"""LBO stress testing on the user's own deal structure."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from ..lbo_engine import LboInputs, run_lbo_model

SHOCKS = {
    "senior_rate": 0.02, "sub_rate": 0.02, "revenue_growth": -0.05,
    "target_ebitda_margin": -0.03, "exit_multiple": -2.0,
}
SCENARIOS = [
    ("Base case", [], "Your current assumptions."),
    ("Rates +200bp", ["senior_rate", "sub_rate"], "All debt costs 2 percentage points more."),
    ("Growth -5pts", ["revenue_growth"], "Revenue grows 5 percentage points slower every year."),
    ("Margin -3pts", ["target_ebitda_margin"], "Exit-year EBITDA margin 3 points lower."),
    ("Exit multiple -2x", ["exit_multiple"], "Exit at two turns of EBITDA below plan."),
    ("Combined downside", list(SHOCKS), "All four shocks at once."),
]


def lbo_stress(company: dict[str, Any], inputs: LboInputs) -> dict[str, Any]:
    results = []
    for name, keys, description in SCENARIOS:
        changes = {key: getattr(inputs, key) + SHOCKS[key] for key in keys}
        if "exit_multiple" in changes:
            changes["exit_multiple"] = max(changes["exit_multiple"], 1.0)
        if "target_ebitda_margin" in changes:
            changes["target_ebitda_margin"] = max(changes["target_ebitda_margin"], 0.01)
        outcome = run_lbo_model(company, replace(inputs, **changes))
        valid = outcome.get("status") in {"VALID", "REVIEW_REQUIRED"}
        results.append({
            "name": name, "description": description, "status": outcome.get("status"),
            "irr": outcome.get("irr") if valid else None, "moic": outcome.get("moic") if valid else None,
            "min_interest_coverage": outcome.get("min_interest_coverage") if valid else None,
            "peak_revolver": outcome.get("peak_revolver") if valid else None,
            "message": None if valid else outcome.get("message"),
        })
    base = results[0]
    return {"status": "VALID" if base["irr"] is not None else base["status"], "currency": (company.get("currency") or "USD").upper(),
            "scenarios": results}
