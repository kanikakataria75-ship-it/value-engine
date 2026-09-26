"""Leveraged buyout engine.

Sources & uses:   Uses = entry EV (EBITDA_0 x entry multiple) + transaction fees
                  Sources = senior debt + subordinated debt (sized in turns of EBITDA) + sponsor equity
Operations:       revenue grows at g; EBITDA margin ramps linearly from the actual margin to the target
Cash waterfall:   levered free cash flow -> mandatory senior amortisation -> revolver repayment ->
                  senior sweep -> subordinated sweep -> cash build. Shortfalls are funded by a revolver.
Returns:          exit equity = exit EBITDA x exit multiple - net debt; IRR = MOIC^(1/N) - 1
Attribution:      EBITDA growth + multiple expansion + deleveraging - fees (+ equity floor) = value created
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..config import LBO_MAX_DEBT_TO_EV, LBO_SENIOR_AMORTIZATION
from .common import flag, is_balance_sheet_financial, num, safe_div


@dataclass
class LboInputs:
    entry_multiple: float
    exit_multiple: float
    senior_debt_turns: float
    sub_debt_turns: float
    senior_rate: float
    sub_rate: float
    revenue_growth: float
    target_ebitda_margin: float
    fees_pct: float = 0.02
    projection_years: int = 5
    tax_rate: float = 0.21
    capex_pct: float | None = None
    da_pct: float | None = None
    nwc_pct: float = 0.05
    senior_amortization: float = LBO_SENIOR_AMORTIZATION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_lbo_model(company: dict[str, Any], inputs: LboInputs) -> dict[str, Any]:
    if is_balance_sheet_financial(company):
        return {"status": "INVALID", "message": "LBOs of banks, insurers and lenders are not modelled: their debt is operating funding, not acquisition leverage."}
    revenue0, ebitda0 = num(company, "revenue"), num(company, "ebitda")
    if not revenue0 or revenue0 <= 0 or ebitda0 is None or ebitda0 <= 0:
        return {"status": "INVALID", "message": "An LBO needs positive revenue and EBITDA."}
    n = int(inputs.projection_years)
    checks = [
        (1 <= n <= 10, "Holding period must be between 1 and 10 years."),
        (inputs.entry_multiple > 0 and inputs.exit_multiple > 0, "Entry and exit multiples must be positive."),
        (inputs.senior_debt_turns >= 0 and inputs.sub_debt_turns >= 0, "Debt turns cannot be negative."),
        (0 <= inputs.senior_rate < 0.5 and 0 <= inputs.sub_rate < 0.5, "Interest rates must be between 0% and 50%."),
        (0 <= inputs.fees_pct < 0.2, "Fees must be between 0% and 20% of EV."),
        (-0.5 < inputs.revenue_growth < 1.0, "Revenue growth must be between -50% and 100%."),
        (0 < inputs.target_ebitda_margin < 1.0, "Target EBITDA margin must be between 0% and 100%."),
    ]
    for ok, message in checks:
        if not ok:
            return {"status": "INVALID", "message": message}

    capex_pct = inputs.capex_pct if inputs.capex_pct is not None else (num(company, "capex") or 0.0) / revenue0
    da_pct = inputs.da_pct if inputs.da_pct is not None else (num(company, "d_and_a") or 0.0) / revenue0
    margin0 = ebitda0 / revenue0
    currency = (company.get("currency") or "USD").upper()

    entry_ev = ebitda0 * inputs.entry_multiple
    fees = entry_ev * inputs.fees_pct
    uses = entry_ev + fees
    senior0 = ebitda0 * inputs.senior_debt_turns
    sub0 = ebitda0 * inputs.sub_debt_turns
    debt0 = senior0 + sub0
    equity0 = uses - debt0
    if equity0 <= 0:
        return {"status": "INVALID", "message": f"Debt ({debt0:,.0f}) funds all uses ({uses:,.0f}); sponsor equity must be positive."}
    revolver_rate = max(inputs.senior_rate - 0.0075, 0.0)  # revolvers price slightly inside term loans

    senior, sub, revolver, cash = senior0, sub0, 0.0, 0.0
    revenue_prev = revenue0
    schedule = []
    for year in range(1, n + 1):
        revenue = revenue0 * (1 + inputs.revenue_growth) ** year
        margin = margin0 + (inputs.target_ebitda_margin - margin0) * year / n
        ebitda = revenue * margin
        da = revenue * da_pct
        ebit = ebitda - da
        interest = senior * inputs.senior_rate + sub * inputs.sub_rate + revolver * revolver_rate
        taxes = max(ebit - interest, 0.0) * inputs.tax_rate
        capex = revenue * capex_pct
        delta_nwc = (revenue - revenue_prev) * inputs.nwc_pct
        levered_fcf = ebitda - taxes - capex - delta_nwc - interest

        mandatory = min(senior, senior0 * inputs.senior_amortization)
        available = levered_fcf - mandatory
        draw = repay = senior_sweep = sub_sweep = 0.0
        if available < 0:
            use_cash = min(cash, -available)
            cash -= use_cash
            draw = -available - use_cash
            revolver += draw
        else:
            repay = min(revolver, available)
            revolver -= repay
            available -= repay
            senior_sweep = min(senior - mandatory, available)
            available -= senior_sweep
            sub_sweep = min(sub, available)
            available -= sub_sweep
            cash += available
        beg_senior, beg_sub = senior, sub
        senior -= mandatory + senior_sweep
        sub -= sub_sweep
        total_debt = senior + sub + revolver
        schedule.append({
            "year": year, "revenue": revenue, "ebitda": ebitda, "ebitda_margin": margin, "d_and_a": da, "ebit": ebit,
            "interest": interest, "taxes": taxes, "capex": capex, "delta_nwc": delta_nwc, "levered_fcf": levered_fcf,
            "mandatory_amortization": mandatory, "senior_sweep": senior_sweep, "sub_sweep": sub_sweep,
            "revolver_draw": draw, "revolver_repayment": repay,
            "beginning_senior": beg_senior, "ending_senior": senior, "beginning_sub": beg_sub, "ending_sub": sub,
            "revolver_balance": revolver, "cash_balance": cash, "total_debt": total_debt,
            "net_debt": total_debt - cash, "leverage": safe_div(total_debt - cash, ebitda),
            "interest_coverage": safe_div(ebitda, interest) if interest > 0 else None,
        })
        revenue_prev = revenue

    last = schedule[-1]
    exit_ebitda = last["ebitda"]
    exit_ev = exit_ebitda * inputs.exit_multiple
    exit_net_debt = last["net_debt"]
    raw_exit_equity = exit_ev - exit_net_debt
    exit_equity = max(raw_exit_equity, 0.0)
    moic = exit_equity / equity0
    irr = moic ** (1.0 / n) - 1.0 if moic > 0 else -1.0
    value_creation = exit_equity - equity0
    attribution = {
        "ebitda_growth": (exit_ebitda - ebitda0) * inputs.entry_multiple,
        "multiple_expansion": (inputs.exit_multiple - inputs.entry_multiple) * exit_ebitda,
        "deleveraging": debt0 - exit_net_debt,
        "fees_and_leakage": -fees,
        "equity_floor": exit_equity - raw_exit_equity,
    }

    entry_leverage = debt0 / ebitda0
    coverages = [row["interest_coverage"] for row in schedule if row["interest_coverage"] is not None]
    min_coverage = min(coverages) if coverages else None
    peak_revolver = max(row["revolver_balance"] for row in schedule)
    flags: list[dict[str, str]] = []
    if entry_leverage > 7.0:
        flags.append(flag("REVIEW", "LBO", "HIGH_LEVERAGE", f"Entry leverage of {entry_leverage:.1f}x EBITDA is above the ~7x lenders typically accept."))
    if debt0 > LBO_MAX_DEBT_TO_EV * entry_ev:
        flags.append(flag("REVIEW", "LBO", "DEBT_TO_EV", f"Debt funds {debt0 / entry_ev:.0%} of EV (> {LBO_MAX_DEBT_TO_EV:.0%})."))
    if min_coverage is not None and min_coverage < 1.5:
        flags.append(flag("REVIEW", "LBO", "WEAK_COVERAGE", f"EBITDA / interest falls to {min_coverage:.2f}x."))
    if peak_revolver > 0:
        flags.append(flag("REVIEW", "LBO", "REVOLVER_DRAWN", f"Cash shortfalls require a revolver draw of up to {peak_revolver:,.0f}."))
    if raw_exit_equity <= 0:
        flags.append(flag("REVIEW", "LBO", "EQUITY_WIPED_OUT", "Exit value does not cover net debt: sponsor equity is lost."))
    elif irr < 0.15:
        flags.append(flag("INFO", "LBO", "BELOW_HURDLE", f"IRR of {irr:.1%} is below the ~15-20% hurdle sponsors typically target."))
    if value_creation > 0 and attribution["multiple_expansion"] > 0.3 * value_creation:
        flags.append(flag("INFO", "LBO", "MULTIPLE_DEPENDENT", "Over 30% of the value created comes from multiple expansion."))
    status = "REVIEW_REQUIRED" if any(f["severity"] == "REVIEW" for f in flags) else "VALID"

    return {
        "status": status,
        "currency": currency,
        "inputs": {**inputs.as_dict(), "capex_pct": capex_pct, "da_pct": da_pct, "revolver_rate": revolver_rate},
        "entry_ebitda": ebitda0,
        "entry_margin": margin0,
        "entry_ev": entry_ev,
        "fees": fees,
        "total_uses": uses,
        "senior_debt": senior0,
        "sub_debt": sub0,
        "total_debt_initial": debt0,
        "sponsor_initial_equity": equity0,
        "equity_contribution_pct": equity0 / uses,
        "entry_leverage": entry_leverage,
        "schedule": schedule,
        "exit_ebitda": exit_ebitda,
        "exit_ev": exit_ev,
        "exit_net_debt": exit_net_debt,
        "exit_equity": exit_equity,
        "moic": moic,
        "irr": irr,
        "value_creation": value_creation,
        "attribution": attribution,
        "min_interest_coverage": min_coverage,
        "peak_revolver": peak_revolver,
        "flags": flags,
        "warnings": [f["message"] for f in flags if f["severity"] == "REVIEW"],
    }
