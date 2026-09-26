"""Company-specific baseline assumptions and the CAPM/WACC builder.

The baseline is the starting point the UI seeds every model with. It is derived from the
company's own statements and history, with each choice explained in `notes`, so no company is
ever modelled with another company's margins or another country's rates.
"""
from __future__ import annotations

import statistics
from typing import Any

from ..config import (
    BASELINE_GROWTH_BOUNDS, BETA_BOUNDS, DEFAULT_NWC_PCT_OF_INCREMENTAL_REVENUE, DEFAULT_PROJECTION_YEARS,
    GROWTH_HISTORY_WEIGHT, LBO_DEFAULT_FEES_PCT, LBO_DEFAULT_SENIOR_TURNS, LBO_DEFAULT_SUB_TURNS,
    LBO_MAX_DEBT_TO_EV, LBO_SENIOR_SPREAD, LBO_SUB_SPREAD, LBO_TAKE_PRIVATE_PREMIUM, MNA_DEFAULT_PREMIUM,
    RONIC_CAP, market_parameters,
)
from .common import clamp, is_balance_sheet_financial, num, safe_div


def history_metrics(history: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [r for r in (history or []) if num(r, "revenue") and num(r, "revenue") > 0]
    rows.sort(key=lambda r: str(r.get("period_end")))
    if not rows:
        return {"years": 0, "revenue_cagr": None, "growth_series": [], "margin_series": [], "periods": []}
    growth_series = [
        {"period_end": cur["period_end"], "growth": cur["revenue"] / prev["revenue"] - 1.0}
        for prev, cur in zip(rows, rows[1:])
    ]
    margin_series = [
        {"period_end": r["period_end"], "margin": r["ebitda"] / r["revenue"]}
        for r in rows if num(r, "ebitda") is not None
    ]
    span = len(rows) - 1
    cagr = (rows[-1]["revenue"] / rows[0]["revenue"]) ** (1.0 / span) - 1.0 if span >= 1 else None
    capex_pcts = [r["capex"] / r["revenue"] for r in rows if num(r, "capex") is not None]
    da_pcts = [r["d_and_a"] / r["revenue"] for r in rows if num(r, "d_and_a") is not None]
    growths = [g["growth"] for g in growth_series]
    margins = [m["margin"] for m in margin_series]
    return {
        "years": len(rows),
        "periods": [r["period_end"] for r in rows],
        "revenue_cagr": cagr,
        "growth_series": growth_series,
        "margin_series": margin_series,
        "growth_volatility": statistics.pstdev(growths) if len(growths) >= 2 else None,
        "margin_volatility": statistics.pstdev(margins) if len(margins) >= 2 else None,
        "margin_average": statistics.fmean(margins) if margins else None,
        "capex_pct_average": statistics.fmean(capex_pcts) if capex_pcts else None,
        "da_pct_average": statistics.fmean(da_pcts) if da_pcts else None,
    }


def select_beta(company: dict[str, Any], regression_beta: float | None) -> tuple[float, str]:
    """Pick the CAPM beta.

    Yahoo's beta is a 5-year monthly regression against the S&P 500. That is appropriate for US
    stocks but meaningless for Indian ones, so non-US companies use a Blume-adjusted 1-year daily
    regression against their own local market index instead.
    """
    provider_beta = num(company, "beta")
    low, high = BETA_BOUNDS
    provider_ok = provider_beta is not None and low <= provider_beta <= high
    regression_ok = regression_beta is not None and regression_beta > 0.1
    local_first = (company.get("currency") or "USD").upper() != "USD"
    if local_first and regression_ok:
        return clamp(regression_beta, low, high), "1Y daily regression vs. local market index (Blume-adjusted)"
    if provider_ok and not local_first:
        return provider_beta, "provider (5Y monthly vs. S&P 500)"
    if regression_ok:
        return clamp(regression_beta, low, high), "1Y daily regression vs. local market index (Blume-adjusted)"
    if provider_ok:
        return provider_beta, "provider (vs. S&P 500; no local regression available)"
    return 1.0, "market default (no valid beta available)"


def build_wacc(company: dict[str, Any], regression_beta: float | None = None) -> dict[str, Any]:
    mp = market_parameters(company.get("currency"))
    beta, beta_source = select_beta(company, regression_beta)
    cost_of_equity = mp.risk_free_rate + beta * mp.equity_risk_premium

    equity = num(company, "market_cap") or 0.0
    debt = max(num(company, "total_debt") or 0.0, 0.0)
    cash = max(num(company, "cash_and_equivalents") or 0.0, 0.0)
    ebitda = num(company, "ebitda")
    net_leverage = safe_div(debt - cash, ebitda) if ebitda and ebitda > 0 else None
    leverage_premium = 0.0
    if net_leverage is not None:
        leverage_premium = 0.025 if net_leverage > 5 else 0.01 if net_leverage > 3 else 0.0
    pre_tax_cost_of_debt = mp.risk_free_rate + mp.credit_spread + leverage_premium
    capital = equity + debt
    weight_debt = debt / capital if capital > 0 else 0.0
    wacc = (1 - weight_debt) * cost_of_equity + weight_debt * pre_tax_cost_of_debt * (1 - mp.tax_rate)
    wacc = clamp(wacc, mp.risk_free_rate + 0.01, 0.25)
    return {
        "wacc": wacc,
        "cost_of_equity": cost_of_equity,
        "pre_tax_cost_of_debt": pre_tax_cost_of_debt,
        "after_tax_cost_of_debt": pre_tax_cost_of_debt * (1 - mp.tax_rate),
        "beta": beta,
        "beta_source": beta_source,
        "provider_beta": num(company, "beta"),
        "regression_beta": regression_beta,
        "risk_free_rate": mp.risk_free_rate,
        "equity_risk_premium": mp.equity_risk_premium,
        "credit_spread": mp.credit_spread,
        "leverage_premium": leverage_premium,
        "tax_rate": mp.tax_rate,
        "weight_equity": 1 - weight_debt,
        "weight_debt": weight_debt,
        "net_debt_to_ebitda": net_leverage,
    }


def company_actuals(company: dict[str, Any]) -> dict[str, Any]:
    mp = market_parameters(company.get("currency"))
    revenue, ebitda, ebit = num(company, "revenue"), num(company, "ebitda"), num(company, "ebit")
    debt = num(company, "total_debt") or 0.0
    cash = num(company, "cash_and_equivalents") or 0.0
    equity_book = num(company, "book_equity")
    market_cap = num(company, "market_cap")
    enterprise_value = market_cap + debt - cash if market_cap else None
    invested_capital = debt + (equity_book or 0.0) - cash if equity_book is not None else None
    roic = safe_div(ebit * (1 - mp.tax_rate) if ebit is not None else None, invested_capital) \
        if invested_capital and invested_capital > 0 else None
    return {
        "ebitda_margin": safe_div(ebitda, revenue),
        "ebit_margin": safe_div(ebit, revenue),
        "net_margin": safe_div(num(company, "net_income"), revenue),
        "capex_pct": safe_div(num(company, "capex"), revenue),
        "da_pct": safe_div(num(company, "d_and_a"), revenue),
        "enterprise_value": enterprise_value,
        "ev_ebitda": safe_div(enterprise_value, ebitda) if ebitda and ebitda > 0 else None,
        "ev_revenue": safe_div(enterprise_value, revenue),
        "pe": safe_div(market_cap, num(company, "net_income")) if (num(company, "net_income") or 0) > 0 else None,
        "pb": safe_div(market_cap, equity_book) if equity_book and equity_book > 0 else None,
        "roe": safe_div(num(company, "net_income"), equity_book) if equity_book and equity_book > 0 else None,
        "roic": roic,
        "invested_capital": invested_capital,
        "net_debt": debt - cash,
        "net_debt_to_ebitda": safe_div(debt - cash, ebitda) if ebitda and ebitda > 0 else None,
    }


def build_baseline(
    company: dict[str, Any],
    history: list[dict[str, Any]] | None = None,
    regression_beta: float | None = None,
) -> dict[str, Any]:
    mp = market_parameters(company.get("currency"))
    actuals = company_actuals(company)
    hist = history_metrics(history)
    wacc_build = build_wacc(company, regression_beta)
    wacc = wacc_build["wacc"]
    financial = is_balance_sheet_financial(company)
    notes: list[str] = []

    low, high = BASELINE_GROWTH_BOUNDS
    if hist["revenue_cagr"] is not None and hist["years"] >= 2:
        raw = GROWTH_HISTORY_WEIGHT * hist["revenue_cagr"] + (1 - GROWTH_HISTORY_WEIGHT) * mp.growth_anchor
        growth = clamp(raw, low, high)
        notes.append(
            f"Revenue growth {growth:.1%}: {GROWTH_HISTORY_WEIGHT:.0%} weight on the {hist['years'] - 1}-year CAGR "
            f"({hist['revenue_cagr']:.1%}) and {1 - GROWTH_HISTORY_WEIGHT:.0%} on {mp.country}'s long-run nominal "
            f"growth anchor ({mp.growth_anchor:.0%}); growth rates mean-revert."
        )
    else:
        growth = mp.growth_anchor
        notes.append(f"Revenue growth {growth:.1%}: no revenue history available, using {mp.country}'s nominal growth anchor.")

    margin = actuals["ebitda_margin"]
    if margin is None:
        margin = 0.0
        notes.append("EBITDA margin unavailable; set to 0% (review before use).")
    else:
        notes.append(f"Target EBITDA margin {margin:.1%}: latest fiscal-year actual (held flat unless you change it).")

    capex_pct = hist.get("capex_pct_average") or actuals["capex_pct"] or 0.0
    da_pct = hist.get("da_pct_average") or actuals["da_pct"] or 0.0
    if hist.get("capex_pct_average") is not None:
        notes.append(f"CapEx {capex_pct:.1%} and D&A {da_pct:.1%} of revenue: {hist['years']}-year averages.")
    else:
        notes.append(f"CapEx {capex_pct:.1%} and D&A {da_pct:.1%} of revenue: latest fiscal year.")

    terminal_growth = min(mp.terminal_growth, wacc - 0.02)
    notes.append(
        f"WACC {wacc:.2%}: CAPM cost of equity {wacc_build['cost_of_equity']:.2%} "
        f"(rf {mp.risk_free_rate:.2%} + beta {wacc_build['beta']:.2f} x ERP {mp.equity_risk_premium:.1%}) "
        f"and after-tax cost of debt {wacc_build['after_tax_cost_of_debt']:.2%} at {wacc_build['weight_debt']:.0%} debt weight."
    )
    roic = actuals["roic"]
    ronic = clamp(roic, wacc, RONIC_CAP) if roic is not None else min(wacc + 0.05, RONIC_CAP)

    ev_ebitda = actuals["ev_ebitda"]
    exit_multiple = clamp(ev_ebitda, 4.0, 30.0) if ev_ebitda else 10.0

    dcf = {
        "revenue_growth": growth,
        "ebitda_margin": margin,
        "wacc": wacc,
        "terminal_growth": terminal_growth,
        "tax_rate": mp.tax_rate,
        "capex_pct": capex_pct,
        "da_pct": da_pct,
        "nwc_pct": DEFAULT_NWC_PCT_OF_INCREMENTAL_REVENUE,
        "ronic": ronic,
        "projection_years": DEFAULT_PROJECTION_YEARS,
        "mid_year_convention": True,
        "terminal_method": "perpetuity",
        "exit_multiple": exit_multiple,
    }

    lbo = None
    ebitda = num(company, "ebitda")
    market_cap = num(company, "market_cap")
    if not financial and ebitda and ebitda > 0 and market_cap:
        entry_ev = market_cap * (1 + LBO_TAKE_PRIVATE_PREMIUM) + actuals["net_debt"]
        entry_multiple = clamp(entry_ev / ebitda, 3.0, 60.0)
        senior_turns, sub_turns = LBO_DEFAULT_SENIOR_TURNS, LBO_DEFAULT_SUB_TURNS
        max_turns = LBO_MAX_DEBT_TO_EV * entry_multiple
        if senior_turns + sub_turns > max_turns:
            scale = max_turns / (senior_turns + sub_turns)
            senior_turns, sub_turns = senior_turns * scale, sub_turns * scale
        lbo = {
            "entry_multiple": round(entry_multiple, 2),
            "exit_multiple": round(entry_multiple, 2),
            "senior_debt_turns": round(senior_turns, 2),
            "sub_debt_turns": round(sub_turns, 2),
            "senior_rate": mp.risk_free_rate + LBO_SENIOR_SPREAD,
            "sub_rate": mp.risk_free_rate + LBO_SUB_SPREAD,
            "revenue_growth": growth,
            "target_ebitda_margin": margin,
            "fees_pct": LBO_DEFAULT_FEES_PCT,
            "projection_years": DEFAULT_PROJECTION_YEARS,
            "tax_rate": mp.tax_rate,
            "capex_pct": capex_pct,
            "da_pct": da_pct,
            "nwc_pct": DEFAULT_NWC_PCT_OF_INCREMENTAL_REVENUE,
        }
        notes.append(
            f"LBO entry {entry_multiple:.1f}x EBITDA: take-private at a {LBO_TAKE_PRIVATE_PREMIUM:.0%} premium to market "
            f"equity plus net debt; exit at the same multiple (no multiple expansion assumed)."
        )

    excess_return = None
    if financial:
        roe = actuals["roe"]
        cost_of_equity = wacc_build["cost_of_equity"]
        if roe is not None:
            roe = clamp(roe, -0.10, 0.40)
            terminal_roe = cost_of_equity + 0.5 * max(roe - cost_of_equity, 0.0)
            excess_return = {
                "roe": roe,
                "terminal_roe": terminal_roe,
                "cost_of_equity": cost_of_equity,
                "book_growth": clamp(min(roe * 0.7, mp.growth_anchor + 0.05), 0.0, 0.20),
                "terminal_growth": min(mp.terminal_growth, cost_of_equity - 0.02),
                "projection_years": DEFAULT_PROJECTION_YEARS,
            }
            notes.append(
                f"Balance-sheet financial: excess-return model. ROE {roe:.1%} vs. cost of equity {cost_of_equity:.1%}; "
                f"excess returns decay halfway toward the cost of equity by year {DEFAULT_PROJECTION_YEARS}."
            )

    return {
        "ticker": company.get("ticker"),
        "currency": (company.get("currency") or "USD").upper(),
        "market": mp.as_dict(),
        "classification": {
            "balance_sheet_financial": financial,
            "intrinsic_model": "excess_return" if financial else "dcf",
        },
        "actuals": actuals,
        "history": hist,
        "wacc_build": wacc_build,
        "dcf": dcf,
        "lbo": lbo,
        "excess_return": excess_return,
        "mna": {"offer_premium_pct": MNA_DEFAULT_PREMIUM},
        "notes": notes,
    }
