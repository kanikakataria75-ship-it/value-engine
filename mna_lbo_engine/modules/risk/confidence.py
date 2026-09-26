"""Valuation confidence: a transparent, fully computed score (no hard-coded labels).

Components (0-100), weighted and renormalised over whichever are available:
  data quality (25%)      - from the data-quality findings
  dispersion (25%)        - Monte Carlo interquartile range relative to the median
  method agreement (20%)  - intrinsic value vs. trading-comps value
  terminal reliance (15%) - share of enterprise value coming from the terminal value
  evidence depth (15%)    - years of fundamentals history and days of price history
"""
from __future__ import annotations

from typing import Any

from ..common import clamp

WEIGHTS = {"data_quality": 0.25, "dispersion": 0.25, "agreement": 0.20, "terminal_reliance": 0.15, "evidence_depth": 0.15}


def valuation_confidence(dq_summary: dict[str, Any], mc: dict[str, Any] | None, intrinsic_price: float | None,
                         comps_price: float | None, tv_share: float | None, history_years: int,
                         price_records: int) -> dict[str, Any]:
    components: list[dict[str, Any]] = []

    counts = dq_summary.get("counts", {})
    components.append({"key": "data_quality", "label": "Data quality", "score": float(dq_summary.get("score", 0)),
                       "detail": f"{counts.get('ERROR', 0)} errors, {counts.get('WARNING', 0)} warnings in the data checks."})

    if mc and mc.get("status") == "VALID":
        m = mc["metrics"]
        median = m["median"]
        rel = (m["p75"] - m["p25"]) / abs(median) if median else None
        score = 100 * clamp(1 - rel / 0.8, 0, 1) if rel is not None else None
        components.append({"key": "dispersion", "label": "Valuation dispersion", "score": score,
                           "detail": f"Monte Carlo interquartile range is {rel:.0%} of the median value." if rel is not None
                           else "Median value is zero."})
    else:
        components.append({"key": "dispersion", "label": "Valuation dispersion", "score": None,
                           "detail": "Monte Carlo simulation unavailable."})

    if intrinsic_price is not None and comps_price is not None and (abs(intrinsic_price) + abs(comps_price)) > 0:
        gap = abs(intrinsic_price - comps_price) / ((abs(intrinsic_price) + abs(comps_price)) / 2)
        components.append({"key": "agreement", "label": "Method agreement", "score": 100 * clamp(1 - gap / 0.6, 0, 1),
                           "detail": f"Intrinsic value and comps median differ by {gap:.0%}."})
    else:
        components.append({"key": "agreement", "label": "Method agreement", "score": None,
                           "detail": "Needs both an intrinsic value and a comps value."})

    if tv_share is not None:
        components.append({"key": "terminal_reliance", "label": "Terminal-value reliance",
                           "score": 100 * clamp((0.95 - tv_share) / 0.35, 0, 1),
                           "detail": f"Terminal value is {tv_share:.0%} of enterprise value."})
    else:
        components.append({"key": "terminal_reliance", "label": "Terminal-value reliance", "score": None,
                           "detail": "Not applicable to this valuation method."})

    history_score = {0: 0, 1: 25, 2: 50, 3: 75}.get(history_years, 100)
    price_score = 100 * clamp(price_records / 240, 0, 1)
    components.append({"key": "evidence_depth", "label": "Evidence depth", "score": (history_score + price_score) / 2,
                       "detail": f"{history_years} years of fundamentals, {price_records} daily prices."})

    available = [c for c in components if c["score"] is not None]
    total_weight = sum(WEIGHTS[c["key"]] for c in available)
    overall = sum(WEIGHTS[c["key"]] * c["score"] for c in available) / total_weight if total_weight else None
    for c in components:
        c["weight"] = WEIGHTS[c["key"]]
    label = None if overall is None else "High" if overall >= 75 else "Moderate" if overall >= 50 else "Low"
    return {"status": "VALID" if overall is not None else "UNAVAILABLE", "score": overall, "label": label,
            "components": components,
            "methodology": "Weighted average of the available components (weights renormalised when one is unavailable)."}
