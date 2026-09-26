"""Expectations Lab: reverse DCF.

Instead of asking "what is the company worth?", ask "what does today's price assume?".
Holding every other assumption at the analyst's scenario, the engine solves for the single value
of each driver that makes the DCF equal the market price:
  * implied revenue growth   (at the scenario margin)
  * implied EBITDA margin    (at the scenario growth)
  * implied terminal growth
  * implied expected return  (the discount rate that equates price and cash flows)
It also traces the growth / margin frontier of all combinations that justify the price, places the
company's actual history on it, and estimates the odds that fundamentals beat what is priced in.
For banks and insurers the equivalent question is the ROE the market is pricing in.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

import numpy as np
from scipy import optimize

from .common import num
from .dcf_engine import DcfInputError, DcfInputs, DcfContext, build_context, project, validate_inputs
from .financials_engine import ExcessReturnInputs, _value_per_share
from .risk.simulation import calibrate_volatility

GROWTH_RANGE = (-0.30, 0.60)
MARGIN_RANGE = (-0.20, 0.90)


def _solve(fn: Callable[[np.ndarray], np.ndarray], target: float, low: float, high: float,
           prefer: float | None = None, points: int = 181) -> float | None:
    """Root of fn(x) = target on [low, high]: grid scan for sign changes, then Brent refinement."""
    grid = np.linspace(low, high, points)
    values = fn(grid) - target
    finite = np.isfinite(values)
    roots = []
    for i in range(points - 1):
        if finite[i] and finite[i + 1] and np.sign(values[i]) != np.sign(values[i + 1]):
            a, b = grid[i], grid[i + 1]
            try:
                roots.append(optimize.brentq(lambda x: float(fn(np.array([x]))[0] - target), a, b, xtol=1e-7))
            except ValueError:
                continue
        elif finite[i] and values[i] == 0:
            roots.append(float(grid[i]))
    if not roots:
        return None
    if prefer is None:
        return float(roots[0])
    return float(min(roots, key=lambda r: abs(r - prefer)))


def _resolved(inputs: DcfInputs, ctx: DcfContext) -> DcfInputs:
    ronic = max(inputs.ronic or max(inputs.wacc, ctx.roic or inputs.wacc), inputs.terminal_growth + 0.01)
    return replace(inputs, ronic=ronic)


def implied_drivers(ctx: DcfContext, inputs: DcfInputs, price: float) -> dict[str, float | None]:
    inputs = _resolved(inputs, ctx)
    growth = _solve(lambda g: project(ctx, inputs, growth=g)["price"], price, *GROWTH_RANGE, prefer=inputs.revenue_growth)
    margin = _solve(lambda m: project(ctx, inputs, margin=m)["price"], price, *MARGIN_RANGE, prefer=inputs.ebitda_margin)
    tg_high = inputs.wacc - 0.005
    terminal = _solve(lambda t: project(ctx, inputs, terminal_growth=t)["price"], price, -0.03, tg_high,
                      prefer=inputs.terminal_growth) if inputs.terminal_method == "perpetuity" else None
    wacc_low = inputs.terminal_growth + 0.005 if inputs.terminal_method == "perpetuity" else 0.01
    implied_return = _solve(lambda w: project(ctx, inputs, wacc=w)["price"], price, wacc_low, 0.40, prefer=inputs.wacc)
    return {"revenue_growth": growth, "ebitda_margin": margin, "terminal_growth": terminal, "expected_return": implied_return}


def frontier(ctx: DcfContext, inputs: DcfInputs, price: float, growth_points: np.ndarray) -> list[dict[str, float]]:
    """Margin required at each growth rate for the DCF to equal the market price."""
    inputs = _resolved(inputs, ctx)
    points = []
    for g in growth_points:
        m = _solve(lambda mm, g=g: project(ctx, inputs, growth=np.full_like(mm, g), margin=mm)["price"], price,
                   *MARGIN_RANGE, prefer=inputs.ebitda_margin, points=111)
        if m is not None:
            points.append({"revenue_growth": float(g), "required_margin": float(m)})
    return points


def _value_surface(ctx: DcfContext, inputs: DcfInputs, frontier_points: list[dict[str, float]],
                   history_points: list[dict[str, Any]], growth_high: float, size: int = 33) -> dict[str, Any]:
    """Share value over a growth x margin grid wide enough to show the frontier, the scenario and history."""
    growths = [inputs.revenue_growth] + [p["revenue_growth"] for p in history_points]
    margins = ([inputs.ebitda_margin, ctx.current_margin] + [p["required_margin"] for p in frontier_points]
               + [p["ebitda_margin"] for p in history_points])
    g_low = max(GROWTH_RANGE[0], min(-0.05, min(growths) - 0.03))
    g_high = min(GROWTH_RANGE[1], max(growth_high, max(growths) + 0.03))
    m_low = max(MARGIN_RANGE[0], min(margins) - 0.08)
    m_high = min(MARGIN_RANGE[1], max(margins) + 0.08)
    g_axis = np.linspace(g_low, g_high, size)
    m_axis = np.linspace(m_low, m_high, size)
    G, M = np.meshgrid(g_axis, m_axis)
    values = project(ctx, inputs, growth=G.ravel(), margin=M.ravel())["price"].reshape(G.shape)
    return {
        "growth": [float(g) for g in g_axis],
        "margin": [float(m) for m in m_axis],
        "values": [[None if not np.isfinite(v) else float(v) for v in row] for row in values],
    }


def _narrative(company: dict[str, Any], inputs: DcfInputs, implied: dict[str, float | None],
               hist: dict[str, Any], price: float, currency: str) -> list[str]:
    name = company.get("company_name") or company.get("ticker")
    years = inputs.projection_years
    lines = []
    g = implied["revenue_growth"]
    if g is None:
        lines.append(f"No growth rate between {GROWTH_RANGE[0]:.0%} and {GROWTH_RANGE[1]:.0%} reconciles the DCF with "
                     f"today's price of {price:,.2f} {currency} at a {inputs.ebitda_margin:.1%} margin; the price is "
                     "driven by factors outside this operating model (or the margin assumption is far from what is priced in).")
    else:
        cagr = hist.get("revenue_cagr")
        comparison = ""
        if cagr is not None:
            gap = g - cagr
            direction = "above" if gap > 0 else "below"
            comparison = f", {abs(gap) * 100:.1f} points {direction} the {hist['years'] - 1}-year historical CAGR of {cagr:.1%}"
        lines.append(f"At {price:,.2f} {currency}, the market is pricing {name} for {g:.1%} annual revenue growth over the next "
                     f"{years} years at a {inputs.ebitda_margin:.1%} EBITDA margin{comparison}.")
    m = implied["ebitda_margin"]
    actual_margin = (num(company, 'ebitda') or 0) / (num(company, 'revenue') or 1)
    if m is not None:
        lines.append(f"Holding growth at {inputs.revenue_growth:.1%}, the price requires the EBITDA margin to reach {m:.1%} "
                     f"by year {years} (latest actual: {actual_margin:.1%}).")
    else:
        lines.append(f"Holding growth at {inputs.revenue_growth:.1%}, no EBITDA margin up to {MARGIN_RANGE[1]:.0%} justifies "
                     "the price: the valuation depends on growth well above your scenario.")
    r = implied["expected_return"]
    if r is not None:
        verdict = "exceeds" if r > inputs.wacc else "falls short of"
        lines.append(f"Buying at today's price on your cash-flow forecast implies an expected return of {r:.1%} a year, "
                     f"which {verdict} the {inputs.wacc:.1%} cost of capital.")
    return lines


def expectations_analysis(company: dict[str, Any], inputs: DcfInputs, history: dict[str, Any] | None,
                          iterations: int = 4000, seed: int = 99) -> dict[str, Any]:
    error = validate_inputs(inputs)
    if error:
        return {"status": "INVALID", "message": error}
    try:
        ctx = build_context(company, inputs.tax_rate)
    except DcfInputError as exc:
        return {"status": "INVALID", "message": str(exc)}
    price = ctx.current_price
    if not price or price <= 0:
        return {"status": "UNAVAILABLE", "message": "No market price to reverse-engineer."}
    resolved = _resolved(inputs, ctx)
    hist = history or {}
    implied = implied_drivers(ctx, resolved, price)
    base_value = float(project(ctx, resolved)["price"][0])

    upper = max(0.40, (implied["revenue_growth"] or 0.0) + 0.10, (hist.get("revenue_cagr") or 0.0) + 0.05)
    growth_grid = np.round(np.linspace(-0.10, min(upper, GROWTH_RANGE[1]), 51), 4)
    frontier_points = frontier(ctx, resolved, price, growth_grid)

    vols = calibrate_volatility(hist)
    rng = np.random.default_rng(seed)
    cov = np.array([[vols["revenue_growth"] ** 2, 0.3 * vols["revenue_growth"] * vols["ebitda_margin"]],
                    [0.3 * vols["revenue_growth"] * vols["ebitda_margin"], vols["ebitda_margin"] ** 2]])
    draws = rng.multivariate_normal([resolved.revenue_growth, resolved.ebitda_margin], cov, size=iterations)
    g_draws = np.clip(draws[:, 0], *GROWTH_RANGE)
    m_draws = np.clip(draws[:, 1], *MARGIN_RANGE)
    values = project(ctx, resolved, growth=g_draws, margin=m_draws)["price"]
    beats = values > price
    odds = float(np.mean(beats))
    sample = rng.choice(iterations, size=min(500, iterations), replace=False)

    history_points = []
    margins = {m["period_end"]: m["margin"] for m in hist.get("margin_series", [])}
    for point in hist.get("growth_series", []):
        if point["period_end"] in margins:
            history_points.append({"period_end": point["period_end"], "revenue_growth": point["growth"],
                                   "ebitda_margin": margins[point["period_end"]]})

    surface = _value_surface(ctx, resolved, frontier_points, history_points, float(growth_grid[-1]))

    gap = (implied["revenue_growth"] - hist["revenue_cagr"]) if implied["revenue_growth"] is not None and hist.get("revenue_cagr") is not None else None
    stance = None
    if gap is not None:
        stance = ("priced for acceleration" if gap > 0.05 else "priced for slowdown" if gap < -0.05 else "priced in line with history")
    return {
        "status": "VALID",
        "method": "dcf",
        "currency": ctx.currency,
        "market_price": price,
        "scenario_value": base_value,
        "scenario_upside": base_value / price - 1,
        "scenario": {k: getattr(resolved, k) for k in ("revenue_growth", "ebitda_margin", "wacc", "terminal_growth",
                                                       "projection_years", "terminal_method")},
        "current_margin": ctx.current_margin,
        "implied": implied,
        "historical": {
            "revenue_cagr": hist.get("revenue_cagr"),
            "margin_average": hist.get("margin_average"),
            "years": hist.get("years", 0),
        },
        "expectations_gap": gap,
        "stance": stance,
        "frontier": frontier_points,
        "history_points": history_points,
        "odds_fundamentals_beat_price": odds,
        "cloud": [{"revenue_growth": float(g_draws[i]), "ebitda_margin": float(m_draws[i]), "beats_price": bool(beats[i]),
                   "value": float(values[i])} for i in sample],
        "surface": surface,
        "input_volatility": {"revenue_growth": vols["revenue_growth"], "ebitda_margin": vols["ebitda_margin"]},
        "narrative": _narrative(company, resolved, implied, hist, price, ctx.currency),
        "methodology": "Each implied driver is solved (grid scan + Brent's method) so the DCF equals the market price with "
                       "all other inputs held at your scenario. The frontier traces the margin required at each growth rate. "
                       "Odds are the share of simulated (growth, margin) outcomes, drawn with the company's historical "
                       "volatility, that are worth more than today's price.",
    }


def financial_expectations(company: dict[str, Any], inputs: ExcessReturnInputs) -> dict[str, Any]:
    book, shares, price = num(company, "book_equity"), num(company, "shares_outstanding"), num(company, "current_price")
    if not book or book <= 0 or not shares or not price:
        return {"status": "UNAVAILABLE", "message": "Book equity, shares or price missing."}
    ke, g = inputs.cost_of_equity, inputs.terminal_growth
    market_pb = price * shares / book
    steady_state_roe = g + market_pb * (ke - g)

    def value_at(terminal_roe: np.ndarray) -> np.ndarray:
        return _value_per_share(book, shares, inputs, np.full_like(terminal_roe, ke), np.full_like(terminal_roe, g), terminal_roe)

    implied_terminal = _solve(value_at, price, -0.10, 0.60, prefer=inputs.terminal_roe)
    scenario_value = float(value_at(np.array([inputs.terminal_roe]))[0])
    lines = [
        f"At {price:,.2f} {(company.get('currency') or 'USD').upper()} ({market_pb:.2f}x book), the market is pricing a "
        f"sustainable ROE of about {steady_state_roe:.1%} against a {ke:.1%} cost of equity; the latest ROE is {inputs.roe:.1%}.",
    ]
    if implied_terminal is not None:
        lines.append(f"With your fade assumptions, the price requires ROE to settle at {implied_terminal:.1%} by year "
                     f"{inputs.projection_years}.")
    return {
        "status": "VALID",
        "method": "excess_return",
        "currency": (company.get("currency") or "USD").upper(),
        "market_price": price,
        "scenario_value": scenario_value,
        "scenario_upside": scenario_value / price - 1,
        "market_pb": market_pb,
        "current_roe": inputs.roe,
        "cost_of_equity": ke,
        "implied_steady_state_roe": steady_state_roe,
        "implied_terminal_roe": implied_terminal,
        "expectations_gap": steady_state_roe - inputs.roe,
        "stance": "priced for ROE expansion" if steady_state_roe > inputs.roe + 0.02 else
                  "priced for ROE compression" if steady_state_roe < inputs.roe - 0.02 else "priced near current ROE",
        "narrative": lines,
        "methodology": "Steady-state justified P/B = (ROE - g) / (Ke - g) solved for ROE; the terminal ROE is also solved "
                       "within the residual-income model holding your other assumptions fixed.",
    }


def radar_row(company: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """One universe-radar row: what each company's price implies versus its own history."""
    row = {
        "ticker": company.get("ticker"), "company_name": company.get("company_name"), "sector": company.get("sector"),
        "industry": company.get("industry"), "currency": (company.get("currency") or "USD").upper(),
        "country": "India" if (company.get("currency") or "").upper() == "INR" else "United States",
        "market_cap": num(company, "market_cap"), "price": num(company, "current_price"),
        "model": baseline["classification"]["intrinsic_model"],
    }
    if row["model"] == "excess_return":
        er = baseline.get("excess_return")
        if not er:
            return {**row, "status": "UNAVAILABLE"}
        result = financial_expectations(company, ExcessReturnInputs(**er))
        if result["status"] != "VALID":
            return {**row, "status": "UNAVAILABLE"}
        return {**row, "status": "VALID", "implied_roe": result["implied_steady_state_roe"], "current_roe": er["roe"],
                "expectations_gap": result["expectations_gap"], "scenario_upside": result["scenario_upside"]}
    try:
        inputs = DcfInputs(**baseline["dcf"])
        ctx = build_context(company, inputs.tax_rate)
    except (DcfInputError, TypeError):
        return {**row, "status": "UNAVAILABLE"}
    price = ctx.current_price
    if not price or validate_inputs(inputs):
        return {**row, "status": "UNAVAILABLE"}
    resolved = _resolved(inputs, ctx)
    growth = _solve(lambda g: project(ctx, resolved, growth=g)["price"], price, *GROWTH_RANGE, prefer=resolved.revenue_growth)
    expected_return = _solve(lambda w: project(ctx, resolved, wacc=w)["price"], price,
                             resolved.terminal_growth + 0.005, 0.40, prefer=resolved.wacc)
    value = float(project(ctx, resolved)["price"][0])
    cagr = baseline["history"].get("revenue_cagr")
    return {
        **row,
        "status": "VALID" if growth is not None else "NOT_REACHABLE",
        "implied_growth": growth,
        "historical_cagr": cagr,
        "baseline_growth": resolved.revenue_growth,
        "expectations_gap": (growth - cagr) if growth is not None and cagr is not None else None,
        "implied_return": expected_return,
        "wacc": resolved.wacc,
        "ebitda_margin": resolved.ebitda_margin,
        "scenario_upside": value / price - 1,
    }


def radar_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dcf_rows = [r for r in rows if r.get("model") == "dcf" and r.get("expectations_gap") is not None]
    fin_rows = [r for r in rows if r.get("model") == "excess_return" and r.get("expectations_gap") is not None]
    by_sector: dict[str, list[float]] = {}
    for r in dcf_rows:
        by_sector.setdefault(r.get("sector") or "Unclassified", []).append(r["implied_growth"])
    return {
        "companies": len(rows),
        "dcf_companies": len(dcf_rows),
        "financial_companies": len(fin_rows),
        "not_reachable": sum(1 for r in rows if r.get("status") == "NOT_REACHABLE"),
        "most_optimistic": sorted(dcf_rows, key=lambda r: r["expectations_gap"], reverse=True)[:10],
        "most_pessimistic": sorted(dcf_rows, key=lambda r: r["expectations_gap"])[:10],
        "sector_median_implied_growth": {s: float(np.median(v)) for s, v in sorted(by_sector.items()) if len(v) >= 3},
        "median_implied_growth": float(np.median([r["implied_growth"] for r in dcf_rows])) if dcf_rows else None,
        "median_historical_cagr": float(np.median([r["historical_cagr"] for r in dcf_rows])) if dcf_rows else None,
    }

