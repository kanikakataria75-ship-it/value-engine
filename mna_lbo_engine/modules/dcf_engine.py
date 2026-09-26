"""Discounted cash flow engine (unlevered free cash flow to the firm).

A single vectorised core projects any number of scenarios at once, so the same code serves the
deterministic DCF, sensitivity grids, Monte Carlo simulation and the reverse DCF.

Model:
  Revenue_t   = Revenue_0 x (1 + g)^t
  Margin_t    = linear ramp from the latest actual margin to the target margin in year N
  UFCF_t      = EBIT_t - tax(EBIT_t) + D&A_t - CapEx_t - NWC% x (Revenue_t - Revenue_{t-1})
  Terminal    = perpetuity on normalised free cash flow  NOPAT_{N+1} x (1 - g / RONIC) / (WACC - g)
                (the value-driver formula: reinvestment is whatever growth at RONIC requires), or
                exit multiple x EBITDA_N.
  Equity      = EV - total debt + cash
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

import numpy as np

from ..config import market_parameters
from .common import flag, num, safe_div


@dataclass
class DcfInputs:
    revenue_growth: float
    ebitda_margin: float            # target margin reached in the final projection year
    wacc: float
    terminal_growth: float
    tax_rate: float
    capex_pct: float
    da_pct: float
    nwc_pct: float = 0.05
    ronic: float | None = None      # return on new invested capital in the terminal period
    projection_years: int = 5
    mid_year_convention: bool = True
    terminal_method: str = "perpetuity"   # "perpetuity" | "exit_multiple"
    exit_multiple: float | None = None
    margin_ramp: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DcfContext:
    """Company facts the projection needs; built once, reused across scenarios."""
    base_revenue: float
    current_margin: float
    total_debt: float
    cash: float
    shares: float
    current_price: float | None
    current_ebitda: float | None
    roic: float | None
    currency: str
    warnings: list[str] = field(default_factory=list)


class DcfInputError(ValueError):
    pass


def build_context(company: dict[str, Any], tax_rate: float) -> DcfContext:
    revenue = num(company, "revenue")
    if revenue is None or revenue <= 0:
        raise DcfInputError("Revenue is missing or non-positive; a revenue-driven DCF is not possible.")
    shares = num(company, "shares_outstanding")
    if shares is None or shares <= 0:
        raise DcfInputError("Shares outstanding are missing; per-share value cannot be computed.")
    debt, cash = num(company, "total_debt"), num(company, "cash_and_equivalents")
    if debt is None or cash is None:
        raise DcfInputError("Total debt or cash is missing, so enterprise value cannot be bridged to equity value.")
    if debt < 0 or cash < 0:
        raise DcfInputError("Debt and cash balances cannot be negative.")
    ebitda = num(company, "ebitda")
    ebit = num(company, "ebit")
    equity_book = num(company, "book_equity")
    invested = debt + (equity_book or 0.0) - cash if equity_book is not None else None
    roic = safe_div(ebit * (1 - tax_rate), invested) if ebit is not None and invested and invested > 0 else None
    return DcfContext(
        base_revenue=revenue,
        current_margin=(ebitda / revenue) if ebitda is not None else 0.0,
        total_debt=debt,
        cash=cash,
        shares=shares,
        current_price=num(company, "current_price"),
        current_ebitda=ebitda,
        roic=roic,
        currency=(company.get("currency") or "USD").upper(),
    )


def _as_array(value: Any) -> np.ndarray:
    return np.atleast_1d(np.asarray(value, dtype=float))


def project(ctx: DcfContext, inputs: DcfInputs, growth: Any = None, margin: Any = None,
            wacc: Any = None, terminal_growth: Any = None) -> dict[str, np.ndarray]:
    """Vectorised projection. Scenario arrays broadcast against each other; returns per-scenario arrays."""
    g = _as_array(inputs.revenue_growth if growth is None else growth)
    m = _as_array(inputs.ebitda_margin if margin is None else margin)
    w = _as_array(inputs.wacc if wacc is None else wacc)
    tg = _as_array(inputs.terminal_growth if terminal_growth is None else terminal_growth)
    g, m, w, tg = np.broadcast_arrays(g, m, w, tg)
    n = int(inputs.projection_years)
    years = np.arange(1, n + 1, dtype=float)

    revenue = ctx.base_revenue * (1.0 + g)[:, None] ** years[None, :]
    if inputs.margin_ramp:
        margins = ctx.current_margin + (m - ctx.current_margin)[:, None] * (years[None, :] / n)
    else:
        margins = np.repeat(m[:, None], n, axis=1)
    ebitda = revenue * margins
    da = revenue * inputs.da_pct
    ebit = ebitda - da
    taxes = np.maximum(ebit, 0.0) * inputs.tax_rate
    nopat = ebit - taxes
    capex = revenue * inputs.capex_pct
    prior = np.concatenate([np.full((revenue.shape[0], 1), ctx.base_revenue), revenue[:, :-1]], axis=1)
    delta_nwc = (revenue - prior) * inputs.nwc_pct
    ufcf = nopat + da - capex - delta_nwc

    timing = years - 0.5 if inputs.mid_year_convention else years
    discount = 1.0 / (1.0 + w)[:, None] ** timing[None, :]
    pv_ufcf = ufcf * discount

    with np.errstate(divide="ignore", invalid="ignore"):
        ebit_next = ebit[:, -1] * (1.0 + tg)
        nopat_next = ebit_next - np.maximum(ebit_next, 0.0) * inputs.tax_rate
        ronic = inputs.ronic if inputs.ronic is not None else np.maximum(w, 0.0)
        ronic = np.maximum(ronic, tg + 0.01)
        normalized_fcf = nopat_next * (1.0 - tg / ronic)
        spread = w - tg
        if inputs.terminal_method == "exit_multiple":
            terminal_value = ebitda[:, -1] * float(inputs.exit_multiple or 0.0)
            tv_timing = float(n)  # exit happens at the end of year N regardless of the mid-year convention
            classic_tv = np.where(spread > 0, ufcf[:, -1] * (1.0 + tg) / spread, np.nan)
        else:
            terminal_value = np.where(spread > 0, normalized_fcf / spread, np.nan)
            tv_timing = n - 0.5 if inputs.mid_year_convention else float(n)
            classic_tv = np.where(spread > 0, ufcf[:, -1] * (1.0 + tg) / spread, np.nan)
        pv_terminal = terminal_value / (1.0 + w) ** tv_timing
        enterprise_value = pv_ufcf.sum(axis=1) + pv_terminal
        equity_value = enterprise_value - ctx.total_debt + ctx.cash
        price = equity_value / ctx.shares

    return {
        "revenue": revenue, "margin": margins, "ebitda": ebitda, "da": da, "ebit": ebit, "taxes": taxes,
        "nopat": nopat, "capex": capex, "delta_nwc": delta_nwc, "ufcf": ufcf, "discount": discount,
        "pv_ufcf": pv_ufcf, "terminal_value": terminal_value, "pv_terminal": pv_terminal,
        "classic_terminal_value": classic_tv, "normalized_fcf": normalized_fcf,
        "enterprise_value": enterprise_value, "equity_value": equity_value, "price": price,
        "growth": g, "target_margin": m, "wacc": w, "terminal_growth": tg,
    }


def scenario_prices(ctx: DcfContext, inputs: DcfInputs, growth: Any = None, margin: Any = None,
                    wacc: Any = None, terminal_growth: Any = None) -> np.ndarray:
    return project(ctx, inputs, growth, margin, wacc, terminal_growth)["price"]


def validate_inputs(inputs: DcfInputs) -> str | None:
    if not 1 <= int(inputs.projection_years) <= 15:
        return "Projection years must be between 1 and 15."
    if inputs.wacc <= 0 or inputs.wacc > 0.5:
        return f"WACC of {inputs.wacc:.2%} is outside the valid range (0%, 50%]."
    if not -0.5 < inputs.revenue_growth < 1.0:
        return "Revenue growth must be between -50% and 100%."
    if not -1.0 < inputs.ebitda_margin < 1.0:
        return "EBITDA margin must be between -100% and 100%."
    if not 0 <= inputs.tax_rate < 1:
        return "Tax rate must be between 0% and 100%."
    if inputs.terminal_method == "perpetuity" and inputs.wacc <= inputs.terminal_growth:
        return (f"Terminal growth ({inputs.terminal_growth:.2%}) must be strictly below WACC ({inputs.wacc:.2%}); "
                "otherwise the perpetuity has no finite value.")
    if inputs.terminal_method == "exit_multiple" and not (inputs.exit_multiple and inputs.exit_multiple > 0):
        return "The exit-multiple method needs a positive EV/EBITDA exit multiple."
    if inputs.terminal_method not in {"perpetuity", "exit_multiple"}:
        return f"Unknown terminal method {inputs.terminal_method!r}."
    return None


def run_dcf(company: dict[str, Any], inputs: DcfInputs) -> dict[str, Any]:
    """Deterministic DCF with a full projection table and diagnostics."""
    error = validate_inputs(inputs)
    if error:
        return {"status": "INVALID", "message": error}
    try:
        ctx = build_context(company, inputs.tax_rate)
    except DcfInputError as exc:
        return {"status": "INVALID", "message": str(exc)}

    ronic = inputs.ronic
    if ronic is None:
        ronic = max(inputs.wacc, ctx.roic or inputs.wacc)
    ronic = max(ronic, inputs.terminal_growth + 0.01)
    resolved = replace(inputs, ronic=ronic)
    out = project(ctx, resolved)
    ev = float(out["enterprise_value"][0])
    pv_terminal = float(out["pv_terminal"][0])
    equity = float(out["equity_value"][0])
    price = float(out["price"][0])
    years = int(resolved.projection_years)

    projections = []
    for i in range(years):
        projections.append({
            "year": i + 1,
            "revenue": float(out["revenue"][0, i]),
            "revenue_growth": float(out["growth"][0]),
            "ebitda": float(out["ebitda"][0, i]),
            "ebitda_margin": float(out["margin"][0, i]),
            "d_and_a": float(out["da"][0, i]),
            "ebit": float(out["ebit"][0, i]),
            "taxes": float(out["taxes"][0, i]),
            "nopat": float(out["nopat"][0, i]),
            "capex": float(out["capex"][0, i]),
            "delta_nwc": float(out["delta_nwc"][0, i]),
            "ufcf": float(out["ufcf"][0, i]),
            "discount_factor": float(out["discount"][0, i]),
            "pv_ufcf": float(out["pv_ufcf"][0, i]),
        })

    mp = market_parameters(ctx.currency)
    flags: list[dict[str, str]] = []
    tv_share = pv_terminal / ev if ev > 0 else None
    if tv_share is not None and tv_share > 0.85:
        flags.append(flag("REVIEW", "DCF", "TV_DOMINANT", f"Terminal value is {tv_share:.0%} of enterprise value; the result rests on long-run assumptions."))
    if resolved.terminal_method == "perpetuity" and resolved.wacc - resolved.terminal_growth < 0.015:
        flags.append(flag("REVIEW", "DCF", "THIN_SPREAD", f"WACC - g spread is only {resolved.wacc - resolved.terminal_growth:.2%}; value is extremely sensitive to both."))
    if resolved.terminal_method == "perpetuity" and resolved.terminal_growth > mp.risk_free_rate:
        flags.append(flag("REVIEW", "DCF", "TG_ABOVE_RF", f"Terminal growth exceeds the {mp.country} risk-free rate ({mp.risk_free_rate:.1%})."))
    if equity < 0:
        flags.append(flag("REVIEW", "DCF", "NEGATIVE_EQUITY", "Implied equity value is negative: projected cash flows do not cover net debt."))
    if any(p["ufcf"] < 0 for p in projections):
        flags.append(flag("INFO", "DCF", "NEGATIVE_FCF", "Free cash flow is negative in at least one projection year (reinvestment exceeds cash earnings)."))
    if abs(resolved.ebitda_margin - ctx.current_margin) > 0.10:
        flags.append(flag("INFO", "DCF", "MARGIN_SHIFT", f"Target margin {resolved.ebitda_margin:.1%} differs from the latest actual {ctx.current_margin:.1%} by more than 10 points."))
    if resolved.revenue_growth > 0.25:
        flags.append(flag("REVIEW", "DCF", "AGGRESSIVE_GROWTH", f"{resolved.revenue_growth:.0%} annual growth for {years} years is aggressive."))

    status = "REVIEW_REQUIRED" if any(f["severity"] == "REVIEW" for f in flags) else "VALID"
    current_price = ctx.current_price
    return {
        "status": status,
        "method": "dcf",
        "ticker": company.get("ticker"),
        "company_name": company.get("company_name"),
        "currency": ctx.currency,
        "inputs": resolved.as_dict(),
        "current_margin": ctx.current_margin,
        "projections": projections,
        "pv_ufcf_sum": float(out["pv_ufcf"][0].sum()),
        "terminal_method": resolved.terminal_method,
        "terminal_value": float(out["terminal_value"][0]),
        "classic_terminal_value": float(out["classic_terminal_value"][0]),
        "terminal_fcf": float(out["normalized_fcf"][0]),
        "pv_terminal_value": pv_terminal,
        "terminal_share_of_ev": tv_share,
        "enterprise_value": ev,
        "total_debt": ctx.total_debt,
        "cash": ctx.cash,
        "net_debt": ctx.total_debt - ctx.cash,
        "equity_value": equity,
        "shares_outstanding": ctx.shares,
        "implied_share_price": price,
        "current_price": current_price,
        "upside": (price / current_price - 1.0) if current_price else None,
        "implied_ev_ebitda": ev / ctx.current_ebitda if ctx.current_ebitda and ctx.current_ebitda > 0 else None,
        "roic": ctx.roic,
        "ronic": ronic,
        "value_creation_spread": (ctx.roic - resolved.wacc) if ctx.roic is not None else None,
        "flags": flags,
        "warnings": [f["message"] for f in flags if f["severity"] == "REVIEW"],
    }


def sensitivity_grids(company: dict[str, Any], inputs: DcfInputs) -> dict[str, Any]:
    """WACC x terminal growth and growth x margin grids of implied share price (vectorised)."""
    error = validate_inputs(inputs)
    if error:
        return {"status": "INVALID", "message": error}
    try:
        ctx = build_context(company, inputs.tax_rate)
    except DcfInputError as exc:
        return {"status": "INVALID", "message": str(exc)}
    ronic = max(inputs.ronic or max(inputs.wacc, ctx.roic or inputs.wacc), inputs.terminal_growth + 0.01)
    resolved = replace(inputs, ronic=ronic)

    wacc_values = [round(inputs.wacc + d, 6) for d in (-0.01, -0.005, 0.0, 0.005, 0.01)]
    tg_values = [round(inputs.terminal_growth + d, 6) for d in (-0.01, -0.005, 0.0, 0.005, 0.01)]
    growth_values = [round(inputs.revenue_growth + d, 6) for d in (-0.04, -0.02, 0.0, 0.02, 0.04)]
    margin_values = [round(inputs.ebitda_margin + d, 6) for d in (-0.04, -0.02, 0.0, 0.02, 0.04)]

    W, T = np.meshgrid(wacc_values, tg_values)
    grid1 = scenario_prices(ctx, resolved, wacc=W.ravel(), terminal_growth=T.ravel()).reshape(W.shape)
    if resolved.terminal_method == "perpetuity":
        grid1 = np.where(W > T, grid1, np.nan)
    G, M = np.meshgrid(growth_values, margin_values)
    grid2 = scenario_prices(ctx, resolved, growth=G.ravel(), margin=M.ravel()).reshape(G.shape)

    def clean(grid: np.ndarray) -> list[list[float | None]]:
        return [[None if not np.isfinite(v) else float(v) for v in row] for row in grid]

    return {
        "status": "VALID",
        "currency": ctx.currency,
        "current_price": ctx.current_price,
        "wacc_values": wacc_values,
        "terminal_growth_values": tg_values,
        "wacc_terminal": clean(grid1),
        "revenue_growth_values": growth_values,
        "ebitda_margin_values": margin_values,
        "growth_margin": clean(grid2),
    }
