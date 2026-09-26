"""M&A accretion / dilution engine.

All figures are expressed in the acquirer's currency; a target reporting in another currency is
restated at a stored, dated FX rate. Consideration can mix new acquirer shares, cash already on
the acquirer's balance sheet (which forgoes interest income) and newly issued debt.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..config import market_parameters
from .common import flag, fmt_money, num, safe_div
from .fx import FxConverter, FxUnavailable, convert_company


@dataclass
class MnaInputs:
    offer_premium_pct: float = 0.25
    pct_stock: float = 0.5
    pct_cash: float = 0.0
    pct_debt: float = 0.5
    debt_interest_rate: float | None = None
    cash_yield: float | None = None
    revenue_synergies: float = 0.0
    incremental_margin: float = 0.20
    cost_synergies: float = 0.0
    integration_costs: float = 0.0
    tax_rate: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


REQUIRED = ("current_price", "shares_outstanding", "net_income")


def run_ma_model(acquirer: dict[str, Any], target: dict[str, Any], inputs: MnaInputs,
                 fx: FxConverter | None = None) -> dict[str, Any]:
    for role, company in (("Acquirer", acquirer), ("Target", target)):
        missing = [f for f in REQUIRED if num(company, f) is None]
        if missing:
            return {"status": "INVALID", "message": f"{role} is missing {', '.join(missing)}."}
        if (num(company, "current_price") or 0) <= 0 or (num(company, "shares_outstanding") or 0) <= 0:
            return {"status": "INVALID", "message": f"{role} price and share count must be positive."}
    if str(acquirer.get("ticker")).upper() == str(target.get("ticker")).upper():
        return {"status": "INVALID", "message": "Acquirer and target must be different companies."}
    mix = inputs.pct_stock + inputs.pct_cash + inputs.pct_debt
    if min(inputs.pct_stock, inputs.pct_cash, inputs.pct_debt) < 0 or abs(mix - 1.0) > 1e-4:
        return {"status": "INVALID", "message": f"Stock + cash + new debt must equal 100% (currently {mix:.1%})."}
    if not -0.5 < inputs.offer_premium_pct < 3.0:
        return {"status": "INVALID", "message": "Offer premium must be between -50% and 300%."}

    acq_ccy = (acquirer.get("currency") or "USD").upper()
    tgt_ccy = (target.get("currency") or "USD").upper()
    mp = market_parameters(acq_ccy)
    tax = inputs.tax_rate if inputs.tax_rate is not None else mp.tax_rate
    debt_rate = inputs.debt_interest_rate if inputs.debt_interest_rate is not None else mp.risk_free_rate + mp.credit_spread
    cash_yield = inputs.cash_yield if inputs.cash_yield is not None else max(mp.risk_free_rate - 0.01, 0.0)

    flags: list[dict[str, str]] = []
    fx_info = None
    target_local = target
    if acq_ccy != tgt_ccy:
        if fx is None:
            return {"status": "INVALID", "message": f"Target reports in {tgt_ccy} but acquirer in {acq_ccy}; no FX converter available."}
        try:
            quote = fx.quote(tgt_ccy, acq_ccy)
        except FxUnavailable as exc:
            return {"status": "INVALID", "message": str(exc)}
        target_local = convert_company(target, quote)
        fx_info = quote.as_dict()
        flags.append(flag("INFO", "M&A", "FX_CONVERTED",
                          f"Target restated from {tgt_ccy} to {acq_ccy} at {quote.rate:,.6g} {acq_ccy}/{tgt_ccy} ({quote.date or 'latest'})."))

    a_price, a_shares, a_ni = num(acquirer, "current_price"), num(acquirer, "shares_outstanding"), num(acquirer, "net_income")
    t_price, t_shares, t_ni = num(target_local, "current_price"), num(target_local, "shares_outstanding"), num(target_local, "net_income")

    offer_price = t_price * (1 + inputs.offer_premium_pct)
    purchase_equity = offer_price * t_shares
    stock_consideration = purchase_equity * inputs.pct_stock
    cash_used = purchase_equity * inputs.pct_cash
    new_debt = purchase_equity * inputs.pct_debt
    new_shares = stock_consideration / a_price

    interest_new_debt = new_debt * debt_rate
    foregone_interest = cash_used * cash_yield
    at_financing_cost = (interest_new_debt + foregone_interest) * (1 - tax)
    pre_tax_synergies = inputs.revenue_synergies * inputs.incremental_margin + inputs.cost_synergies
    at_synergies = pre_tax_synergies * (1 - tax)
    at_integration = inputs.integration_costs * (1 - tax)

    pro_forma_ni_run_rate = a_ni + t_ni + at_synergies - at_financing_cost
    pro_forma_ni_year1 = pro_forma_ni_run_rate - at_integration
    pro_forma_shares = a_shares + new_shares
    standalone_eps = a_ni / a_shares
    eps_year1 = pro_forma_ni_year1 / pro_forma_shares
    eps_run_rate = pro_forma_ni_run_rate / pro_forma_shares

    def change(eps: float) -> tuple[float, float | None]:
        delta = eps - standalone_eps
        return delta, (delta / abs(standalone_eps)) if standalone_eps else None

    delta_y1, pct_y1 = change(eps_year1)
    delta_rr, pct_rr = change(eps_run_rate)

    needed_ni = standalone_eps * pro_forma_shares
    shortfall = needed_ni - (a_ni + t_ni - at_financing_cost - at_integration)
    break_even = max(shortfall, 0.0) / (1 - tax) if tax < 1 else None

    a_debt, a_cash = num(acquirer, "total_debt") or 0.0, num(acquirer, "cash_and_equivalents") or 0.0
    t_debt, t_cash = num(target_local, "total_debt") or 0.0, num(target_local, "cash_and_equivalents") or 0.0
    t_ebitda, a_ebitda = num(target_local, "ebitda"), num(acquirer, "ebitda")
    offer_ev = purchase_equity + t_debt - t_cash
    combined_ebitda = (a_ebitda or 0.0) + (t_ebitda or 0.0)
    pro_forma_debt = a_debt + t_debt + new_debt
    pro_forma_net_debt = pro_forma_debt - (a_cash - cash_used) - t_cash
    pf_leverage = safe_div(pro_forma_net_debt, combined_ebitda) if combined_ebitda > 0 else None

    acquirer_pe = safe_div(a_price, standalone_eps) if standalone_eps > 0 else None
    pe_paid = safe_div(purchase_equity, t_ni) if t_ni > 0 else None

    if pct_y1 is not None and pct_y1 < 0:
        flags.append(flag("INFO", "M&A", "DILUTIVE",
                          f"Year-1 EPS is {abs(pct_y1):.1%} dilutive; about {fmt_money(break_even, acq_ccy)} of pre-tax synergies a year are needed to break even."))
    if cash_used > a_cash:
        flags.append(flag("REVIEW", "M&A", "INSUFFICIENT_CASH",
                          f"Cash consideration ({fmt_money(cash_used, acq_ccy)}) exceeds the acquirer's cash balance ({fmt_money(a_cash, acq_ccy)})."))
    if pf_leverage is not None and pf_leverage > 4.0:
        flags.append(flag("REVIEW", "M&A", "HIGH_LEVERAGE", f"Pro forma net debt / EBITDA of {pf_leverage:.1f}x is above 4x."))
    if pre_tax_synergies > 0 and break_even and break_even > 3 * pre_tax_synergies:
        flags.append(flag("REVIEW", "M&A", "SYNERGY_GAP",
                          f"Break-even synergies are {break_even / pre_tax_synergies:.1f}x the synergies entered."))
    if inputs.offer_premium_pct > 0.6:
        flags.append(flag("REVIEW", "M&A", "HIGH_PREMIUM", f"A {inputs.offer_premium_pct:.0%} premium is well above typical control premiums (20-40%)."))
    if standalone_eps <= 0:
        flags.append(flag("REVIEW", "M&A", "LOSS_MAKING_ACQUIRER", "Acquirer EPS is negative; accretion percentages are not meaningful."))
    if t_ni <= 0:
        flags.append(flag("INFO", "M&A", "LOSS_MAKING_TARGET", "Target is loss-making; the deal is dilutive before synergies."))
    if acquirer_pe and pe_paid and inputs.pct_stock > 0:
        rule = "accretive" if acquirer_pe > pe_paid else "dilutive"
        flags.append(flag("INFO", "M&A", "PE_RULE",
                          f"Acquirer P/E {acquirer_pe:.1f}x vs. P/E paid {pe_paid:.1f}x: the stock-funded part is {rule} before synergies."))

    status = "REVIEW_REQUIRED" if any(f["severity"] == "REVIEW" for f in flags) else "VALID"
    return {
        "status": status,
        "currency": acq_ccy,
        "target_currency": tgt_ccy,
        "fx": fx_info,
        "acquirer_ticker": acquirer.get("ticker"),
        "target_ticker": target.get("ticker"),
        "inputs": {**inputs.as_dict(), "tax_rate": tax, "debt_interest_rate": debt_rate, "cash_yield": cash_yield},
        "offer_price": offer_price,
        "offer_price_target_currency": num(target, "current_price") * (1 + inputs.offer_premium_pct),
        "total_purchase_price": purchase_equity,
        "offer_enterprise_value": offer_ev,
        "implied_ev_ebitda": safe_div(offer_ev, t_ebitda) if t_ebitda and t_ebitda > 0 else None,
        "implied_pe": pe_paid,
        "acquirer_pe": acquirer_pe,
        "stock_consideration": stock_consideration,
        "cash_consideration": cash_used,
        "new_debt": new_debt,
        "new_shares_issued": new_shares,
        "new_debt_interest_pre_tax": interest_new_debt,
        "foregone_interest_pre_tax": foregone_interest,
        "after_tax_financing_cost": at_financing_cost,
        "pre_tax_synergies": pre_tax_synergies,
        "after_tax_synergies": at_synergies,
        "after_tax_integration": at_integration,
        "acquirer_net_income": a_ni,
        "target_net_income": t_ni,
        "pro_forma_net_income": pro_forma_ni_year1,
        "pro_forma_net_income_run_rate": pro_forma_ni_run_rate,
        "pro_forma_shares": pro_forma_shares,
        "acquirer_standalone_eps": standalone_eps,
        "post_deal_eps": eps_year1,
        "post_deal_eps_run_rate": eps_run_rate,
        "eps_change": delta_y1,
        "eps_change_pct": pct_y1,
        "eps_change_run_rate": delta_rr,
        "eps_change_pct_run_rate": pct_rr,
        "is_accretive": delta_y1 >= 0,
        "break_even_pre_tax_synergy": break_even,
        "ownership_acquirer": a_shares / pro_forma_shares,
        "ownership_target": new_shares / pro_forma_shares,
        "pro_forma_debt": pro_forma_debt,
        "pro_forma_net_debt_to_ebitda": pf_leverage,
        "acquirer_cash": a_cash,
        "flags": flags,
        "warnings": [f["message"] for f in flags if f["severity"] == "REVIEW"],
    }
