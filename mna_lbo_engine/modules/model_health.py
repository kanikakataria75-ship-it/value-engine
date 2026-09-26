"""Model health and scenario scorecard.

Aggregates the structured flags that every engine emits plus the data-quality findings into one
status:
  INVALID          an engine could not produce a result, or the data has hard errors
  REVIEW_REQUIRED  results exist but an assumption or data point needs a second look
  VALID            nothing to review
A dilutive deal or a low IRR is an outcome, not a model error, so those are INFO flags.
"""
from __future__ import annotations

from typing import Any

from .common import flag


def evaluate_model_health(results: dict[str, dict[str, Any] | None], data_issues: list[dict[str, Any]]) -> dict[str, Any]:
    flags: list[dict[str, str]] = []
    for module, result in results.items():
        if result is None:
            continue
        status = result.get("status")
        if status == "INVALID":
            flags.append(flag("INVALID", module, "ENGINE_INVALID", result.get("message") or f"{module} inputs are invalid."))
        elif status == "UNAVAILABLE":
            flags.append(flag("INFO", module, "ENGINE_UNAVAILABLE", result.get("message") or f"{module} is unavailable."))
        flags.extend(result.get("flags") or [])
    for issue in data_issues:
        if issue["severity"] == "ERROR":
            flags.append(flag("INVALID", "DATA", issue["rule"], issue["message"]))
        elif issue["severity"] == "WARNING":
            flags.append(flag("REVIEW", "DATA", issue["rule"], issue["message"]))

    order = {"INVALID": 0, "REVIEW": 1, "INFO": 2}
    flags.sort(key=lambda f: order.get(f["severity"], 3))
    if any(f["severity"] == "INVALID" for f in flags):
        status = "INVALID"
    elif any(f["severity"] == "REVIEW" for f in flags):
        status = "REVIEW_REQUIRED"
    else:
        status = "VALID"
    counts = {level: sum(1 for f in flags if f["severity"] == level) for level in ("INVALID", "REVIEW", "INFO")}
    return {"status": status, "flags": flags, "counts": counts}


def scenario_scorecard(intrinsic: dict[str, Any] | None, mna: dict[str, Any] | None, lbo: dict[str, Any] | None) -> dict[str, Any]:
    """Transparent 0-100 scorecard. Components that are not applicable are skipped, not scored as zero."""
    components: list[dict[str, Any]] = []

    def usable(result: dict[str, Any] | None) -> bool:
        return bool(result) and result.get("status") in {"VALID", "REVIEW_REQUIRED"}

    if usable(intrinsic) and intrinsic.get("upside") is not None:
        upside = intrinsic["upside"]
        points = 25 if upside > 0.2 else 15 if upside > 0 else 5 if upside > -0.2 else 0
        components.append({"label": "Intrinsic value vs. market", "points": points, "max": 25,
                           "detail": f"Intrinsic value is {upside:+.0%} vs. the market price."})
    if usable(mna):
        pct = mna.get("eps_change_pct_run_rate")
        if pct is not None:
            points = 25 if pct > 0.02 else 15 if pct >= 0 else 5 if pct > -0.05 else 0
            components.append({"label": "Run-rate EPS accretion", "points": points, "max": 25,
                               "detail": f"Run-rate EPS change {pct:+.1%}."})
        needed, entered = mna.get("break_even_pre_tax_synergy") or 0.0, mna.get("pre_tax_synergies") or 0.0
        points = 25 if needed <= 0 else 15 if entered >= needed else 0
        components.append({"label": "Synergy dependence", "points": points, "max": 25,
                           "detail": "Accretive before synergies." if needed <= 0 else
                           f"Needs {needed:,.0f} of pre-tax synergies; {entered:,.0f} entered."})
    if usable(lbo):
        irr = lbo.get("irr")
        points = 25 if irr >= 0.20 else 15 if irr >= 0.15 else 5 if irr >= 0.10 else 0
        components.append({"label": "Sponsor returns", "points": points, "max": 25, "detail": f"LBO IRR {irr:.1%}."})

    total_max = sum(c["max"] for c in components)
    score = 100.0 * sum(c["points"] for c in components) / total_max if total_max else None
    return {"score": score, "components": components,
            "note": "Scores only the analyses that apply to this company and scenario."}
