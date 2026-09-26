"""Trading comparables.

Peer selection scores same-sector candidates on industry match, country match and size
proximity (log distance of USD market caps), so a US company is benchmarked against similar
US companies before anything else. Multiples are ratios within each company's own currency,
so they are comparable across currencies; implied values are expressed in the target's currency.
"""
from __future__ import annotations

import math
from typing import Any, Callable

import numpy as np

from .common import country_of, is_balance_sheet_financial, num, safe_div

MULTIPLE_BOUNDS = {"ev_revenue": (0.0, 40.0), "ev_ebitda": (0.0, 60.0), "pe": (0.0, 100.0), "pb": (0.0, 20.0)}
MULTIPLE_LABELS = {"ev_revenue": "EV / Revenue", "ev_ebitda": "EV / EBITDA", "pe": "P / E", "pb": "P / B"}


def company_multiples(company: dict[str, Any]) -> dict[str, float | None]:
    market_cap = num(company, "market_cap")
    financial = is_balance_sheet_financial(company)
    ev = None
    if market_cap is not None and not financial:
        ev = market_cap + (num(company, "total_debt") or 0.0) - (num(company, "cash_and_equivalents") or 0.0)
    revenue, ebitda, net_income, book = (num(company, k) for k in ("revenue", "ebitda", "net_income", "book_equity"))
    return {
        "ev_revenue": safe_div(ev, revenue) if revenue and revenue > 0 else None,
        "ev_ebitda": safe_div(ev, ebitda) if ebitda and ebitda > 0 else None,
        "pe": safe_div(market_cap, net_income) if net_income and net_income > 0 else None,
        "pb": safe_div(market_cap, book) if book and book > 0 else None,
    }


def select_peers(target: dict[str, Any], candidates: list[dict[str, Any]], to_usd: Callable[[Any, str | None], float | None],
                 max_peers: int = 12) -> list[dict[str, Any]]:
    target_financial = is_balance_sheet_financial(target)
    target_cap = to_usd(num(target, "market_cap"), target.get("currency"))
    target_country = country_of(target)
    target_industry = str(target.get("industry") or "").lower()
    scored = []
    for peer in candidates:
        if is_balance_sheet_financial(peer) != target_financial:
            continue
        peer_cap = to_usd(num(peer, "market_cap"), peer.get("currency"))
        if not peer_cap or peer_cap <= 0:
            continue
        same_industry = bool(target_industry) and str(peer.get("industry") or "").lower() == target_industry
        same_country = country_of(peer) == target_country
        size_distance = abs(math.log(peer_cap / target_cap)) if target_cap and target_cap > 0 else 0.0
        score = 3.0 * same_industry + 2.0 * same_country - size_distance
        scored.append({**peer, "_score": score, "_same_industry": same_industry, "_same_country": same_country,
                       "_market_cap_usd": peer_cap})
    scored.sort(key=lambda p: p["_score"], reverse=True)
    return scored[:max_peers]


def _stats(values: list[float]) -> dict[str, Any]:
    arr = np.asarray(values, dtype=float)
    return {
        "n": int(arr.size),
        "min": float(arr.min()), "p25": float(np.percentile(arr, 25)), "median": float(np.median(arr)),
        "mean": float(arr.mean()), "p75": float(np.percentile(arr, 75)), "max": float(arr.max()),
    }


def _implied_price(target: dict[str, Any], key: str, multiple: float) -> float | None:
    shares = num(target, "shares_outstanding")
    if not shares:
        return None
    debt = num(target, "total_debt") or 0.0
    cash = num(target, "cash_and_equivalents") or 0.0
    if key in {"ev_revenue", "ev_ebitda"}:
        metric = num(target, "revenue" if key == "ev_revenue" else "ebitda")
        if metric is None or metric <= 0:
            return None
        return (metric * multiple - debt + cash) / shares
    metric = num(target, "net_income" if key == "pe" else "book_equity")
    if metric is None or metric <= 0:
        return None
    return metric * multiple / shares


def run_trading_comps(target: dict[str, Any], peers: list[dict[str, Any]]) -> dict[str, Any]:
    if len(peers) < 3:
        return {"status": "UNAVAILABLE", "message": "Fewer than three comparable companies are available in this sector."}
    financial = is_balance_sheet_financial(target)
    keys = ["pe", "pb"] if financial else ["ev_ebitda", "ev_revenue", "pe"]
    primary = "pb" if financial else "ev_ebitda"

    rows, samples, excluded = [], {k: [] for k in keys}, {k: 0 for k in keys}
    for peer in peers:
        multiples = company_multiples(peer)
        row = {
            "ticker": peer.get("ticker"), "company_name": peer.get("company_name"), "country": country_of(peer),
            "industry": peer.get("industry"), "currency": peer.get("currency"),
            "market_cap_usd": peer.get("_market_cap_usd"), "same_industry": peer.get("_same_industry"),
            "similarity": peer.get("_score"),
        }
        for key in ("ev_revenue", "ev_ebitda", "pe", "pb"):
            value = multiples[key]
            low, high = MULTIPLE_BOUNDS[key]
            in_range = value is not None and low < value <= high
            row[key] = value
            if key in keys:
                if in_range:
                    samples[key].append(value)
                elif value is not None:
                    excluded[key] += 1
        rows.append(row)

    distribution, implied = {}, {}
    for key in keys:
        if len(samples[key]) >= 3:
            stats = _stats(samples[key])
            distribution[key] = {**stats, "label": MULTIPLE_LABELS[key], "excluded_outliers": excluded[key]}
            implied[key] = {
                "label": MULTIPLE_LABELS[key],
                "low": _implied_price(target, key, stats["p25"]),
                "mid": _implied_price(target, key, stats["median"]),
                "high": _implied_price(target, key, stats["p75"]),
            }
    if primary not in implied or implied[primary]["mid"] is None:
        fallback = next((k for k in keys if k in implied and implied[k]["mid"] is not None), None)
        if fallback is None:
            return {"status": "UNAVAILABLE", "message": "Peers lack enough valid multiples to value the target.", "peers": rows}
        primary = fallback

    target_multiples = company_multiples(target)
    current_price = num(target, "current_price")
    mid = implied[primary]["mid"]
    return {
        "status": "VALID",
        "currency": (target.get("currency") or "USD").upper(),
        "primary_multiple": primary,
        "primary_label": MULTIPLE_LABELS[primary],
        "implied_share_price_median": mid,
        "implied_range": implied[primary],
        "implied_by_multiple": implied,
        "upside": (mid / current_price - 1.0) if mid and current_price else None,
        "target_multiples": target_multiples,
        "peers": rows,
        "peer_count": len(rows),
        "same_industry_count": sum(1 for r in rows if r["same_industry"]),
        "distribution": distribution,
        "methodology": "Peers scored on industry (+3), country (+2) and size proximity (-|ln cap ratio|); "
                       "medians of in-range multiples; implied range = 25th-75th percentile.",
    }


def run_transaction_comps(target: dict[str, Any], transactions: list[dict[str, Any]]) -> dict[str, Any]:
    """Precedent transactions require a verified deal database; the engine never invents one."""
    if not transactions:
        return {"status": "UNAVAILABLE", "message": "No verified precedent-transaction dataset is configured."}
    values = [t["ev_ebitda"] for t in transactions if num(t, "ev_ebitda")]
    if len(values) < 3:
        return {"status": "UNAVAILABLE", "message": "Fewer than three precedent transactions with EV/EBITDA."}
    stats = _stats(values)
    return {"status": "VALID", "distribution": {"ev_ebitda": stats},
            "implied_share_price_median": _implied_price(target, "ev_ebitda", stats["median"])}
