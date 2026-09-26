"""Excess-return (residual income) valuation for banks, insurers and lenders.

For balance-sheet financials, debt is raw material rather than financing and free cash flow is
not meaningful, so value is anchored on book equity and the spread between ROE and the cost of
equity:

  RI_t    = (ROE_t - Ke) x B_{t-1}          ROE fades linearly from current to terminal ROE
  B_t     = B_{t-1} x (1 + book growth)
  Value   = B_0 + sum PV(RI_t) + PV( (ROE_T - Ke) x B_N / (Ke - g) )
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from .common import flag, num


@dataclass
class ExcessReturnInputs:
    roe: float
    terminal_roe: float
    cost_of_equity: float
    book_growth: float
    terminal_growth: float
    projection_years: int = 5

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _value_per_share(book: float, shares: float, inputs: ExcessReturnInputs,
                     ke: np.ndarray, g: np.ndarray, terminal_roe: np.ndarray | None = None) -> np.ndarray:
    n = int(inputs.projection_years)
    t_roe = np.full_like(ke, inputs.terminal_roe) if terminal_roe is None else terminal_roe
    value = np.full_like(ke, book, dtype=float)
    b_prev = np.full_like(ke, book, dtype=float)
    for t in range(1, n + 1):
        roe_t = inputs.roe + (t_roe - inputs.roe) * t / n
        value = value + (roe_t - ke) * b_prev / (1 + ke) ** t
        b_prev = b_prev * (1 + inputs.book_growth)
    with np.errstate(divide="ignore", invalid="ignore"):
        tv = np.where(ke > g, (t_roe - ke) * b_prev / (ke - g), np.nan)
    value = value + tv / (1 + ke) ** n
    return value / shares


def run_excess_return(company: dict[str, Any], inputs: ExcessReturnInputs) -> dict[str, Any]:
    book, shares = num(company, "book_equity"), num(company, "shares_outstanding")
    if book is None or book <= 0:
        return {"status": "INVALID", "message": "Book equity is missing or negative; an excess-return valuation is not possible."}
    if shares is None or shares <= 0:
        return {"status": "INVALID", "message": "Shares outstanding are missing."}
    if inputs.cost_of_equity <= inputs.terminal_growth:
        return {"status": "INVALID", "message": "Terminal growth must be below the cost of equity."}
    if not 1 <= int(inputs.projection_years) <= 15:
        return {"status": "INVALID", "message": "Projection years must be between 1 and 15."}

    ke = inputs.cost_of_equity
    n = int(inputs.projection_years)
    schedule, b_prev, pv_sum = [], book, 0.0
    for t in range(1, n + 1):
        roe_t = inputs.roe + (inputs.terminal_roe - inputs.roe) * t / n
        net_income = roe_t * b_prev
        residual = (roe_t - ke) * b_prev
        b_next = b_prev * (1 + inputs.book_growth)
        pv = residual / (1 + ke) ** t
        pv_sum += pv
        schedule.append({
            "year": t, "opening_book": b_prev, "roe": roe_t, "net_income": net_income,
            "equity_charge": ke * b_prev, "residual_income": residual, "closing_book": b_next,
            "implied_payout": net_income - (b_next - b_prev), "pv_residual_income": pv,
        })
        b_prev = b_next
    terminal_value = (inputs.terminal_roe - ke) * b_prev / (ke - inputs.terminal_growth)
    pv_terminal = terminal_value / (1 + ke) ** n
    equity_value = book + pv_sum + pv_terminal
    price = equity_value / shares
    current_price = num(company, "current_price")
    market_cap = num(company, "market_cap")
    market_pb = market_cap / book if market_cap else None
    implied_roe = inputs.terminal_growth + market_pb * (ke - inputs.terminal_growth) if market_pb else None

    flags = []
    if any(row["implied_payout"] < 0 for row in schedule):
        flags.append(flag("REVIEW", "EXCESS_RETURN", "BOOK_GROWTH_ABOVE_ROE",
                          "Book growth exceeds earnings in some years, which would require new equity issuance."))
    if inputs.roe < ke:
        flags.append(flag("INFO", "EXCESS_RETURN", "ROE_BELOW_KE",
                          f"Current ROE ({inputs.roe:.1%}) is below the cost of equity ({ke:.1%}): growth destroys value."))
    status = "REVIEW_REQUIRED" if any(f["severity"] == "REVIEW" for f in flags) else "VALID"
    return {
        "status": status,
        "method": "excess_return",
        "ticker": company.get("ticker"),
        "currency": (company.get("currency") or "USD").upper(),
        "inputs": inputs.as_dict(),
        "book_equity": book,
        "book_value_per_share": book / shares,
        "schedule": schedule,
        "pv_residual_income_sum": pv_sum,
        "terminal_value": terminal_value,
        "pv_terminal_value": pv_terminal,
        "equity_value": equity_value,
        "shares_outstanding": shares,
        "implied_share_price": price,
        "current_price": current_price,
        "upside": (price / current_price - 1.0) if current_price else None,
        "justified_pb": equity_value / book,
        "market_pb": market_pb,
        "market_implied_roe": implied_roe,
        "flags": flags,
        "warnings": [f["message"] for f in flags if f["severity"] == "REVIEW"],
    }


def excess_return_sensitivity(company: dict[str, Any], inputs: ExcessReturnInputs) -> dict[str, Any]:
    book, shares = num(company, "book_equity"), num(company, "shares_outstanding")
    if not book or book <= 0 or not shares:
        return {"status": "INVALID", "message": "Book equity or shares missing."}
    ke_values = [round(inputs.cost_of_equity + d, 6) for d in (-0.01, -0.005, 0.0, 0.005, 0.01)]
    g_values = [round(inputs.terminal_growth + d, 6) for d in (-0.01, -0.005, 0.0, 0.005, 0.01)]
    roe_values = [round(inputs.terminal_roe + d, 6) for d in (-0.03, -0.015, 0.0, 0.015, 0.03)]
    K, G = np.meshgrid(ke_values, g_values)
    grid1 = _value_per_share(book, shares, inputs, K.ravel(), G.ravel()).reshape(K.shape)
    K2, R = np.meshgrid(ke_values, roe_values)
    grid2 = _value_per_share(book, shares, inputs, K2.ravel(), np.full(K2.size, inputs.terminal_growth), R.ravel()).reshape(K2.shape)

    def clean(grid: np.ndarray) -> list[list[float | None]]:
        return [[None if not np.isfinite(v) else float(v) for v in row] for row in grid]

    return {
        "status": "VALID",
        "cost_of_equity_values": ke_values,
        "terminal_growth_values": g_values,
        "terminal_roe_values": roe_values,
        "ke_growth": clean(grid1),
        "ke_roe": clean(grid2),
    }
