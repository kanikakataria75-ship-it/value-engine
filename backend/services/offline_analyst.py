"""Rule-based analyst used when no LLM provider is configured or every provider fails.

It answers from the same computed context the LLM receives, so every number it quotes comes from
the engines. Answers are clearly labelled as rule-based by the orchestrator.
"""
from __future__ import annotations

from typing import Any


def _money(value: Any, currency: str, precise: bool = False) -> str:
    if value is None:
        return "n/a"
    value = float(value)
    sign, value = ("-" if value < 0 else ""), abs(value)
    symbol = "₹" if currency == "INR" else "$"
    if precise:
        return f"{sign}{symbol}{value:,.2f}"
    if currency == "INR":
        crore = value / 1e7
        return f"{sign}{symbol}{crore:,.0f} Cr" if crore >= 1 else f"{sign}{symbol}{value:,.0f}"
    for divisor, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if value >= divisor:
            return f"{sign}{symbol}{value / divisor:,.1f}{suffix}"
    return f"{sign}{symbol}{value:,.0f}"


def _pct(value: Any, digits: int = 1) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.{digits}f}%"


INTENTS = [
    ("expectations", ("priced", "pricing in", "price in", "expect", "implied", "reverse", "market think", "baked")),
    ("mna", ("m&a", "acqui", "accret", "dilut", "merger", "synerg")),
    ("lbo", ("lbo", "buyout", "sponsor", "irr", "leverage")),
    ("comps", ("comp", "peer", "multiple", "relative")),
    ("risk", ("risk", "var", "volatil", "default", "merton", "tail", "regime", "downside risk")),
    ("bull", ("bull", "upside case", "optimis", "go right")),
    ("bear", ("bear", "downside case", "pessimis", "go wrong")),
    ("assumptions", ("assumption", "matter", "sensitiv", "driver", "driving")),
    ("wacc", ("wacc", "discount rate", "cost of capital", "beta", "cost of equity")),
    ("valuation", ("valu", "worth", "dcf", "intrinsic", "explain", "fair value", "price target")),
]


def detect_intent(message: str) -> str:
    text = message.lower()
    for intent, keywords in INTENTS:
        if any(k in text for k in keywords):
            return intent
    return "overview"


def _valuation(ctx: dict[str, Any]) -> list[str]:
    c, v = ctx["company"], ctx.get("intrinsic") or {}
    ccy = c["currency"]
    if not v:
        return ["The intrinsic valuation is unavailable for this company with the current inputs."]
    model = "residual-income (excess return) model" if ctx.get("valuation_model") == "excess_return" else "DCF"
    lines = [f"**{c['name']}** is worth about **{_money(v.get('implied_share_price'), ccy, True)} per share** on your {model}, "
             f"versus a market price of {_money(c.get('price'), ccy, True)} ({_pct(v.get('upside'))} upside/downside)."]
    a = ctx.get("assumptions") or {}
    if ctx.get("valuation_model") == "dcf":
        lines.append(f"- Revenue grows {_pct(a.get('revenue_growth'))} a year for {a.get('projection_years')} years; the EBITDA margin moves "
                     f"to {_pct(a.get('ebitda_margin'))} (latest actual {_pct(ctx['fundamentals'].get('ebitda_margin'))}).")
        lines.append(f"- Cash flows are discounted at a {_pct(a.get('wacc'), 2)} WACC with {_pct(a.get('terminal_growth'))} terminal growth; "
                     f"the terminal value is {_pct(v.get('terminal_share_of_ev'), 0)} of enterprise value.")
        lines.append(f"- Enterprise value {_money(v.get('enterprise_value'), ccy)} less net debt {_money(v.get('net_debt'), ccy)} "
                     f"gives equity value {_money(v.get('equity_value'), ccy)}.")
    else:
        lines.append(f"- ROE {_pct(a.get('roe'))} fades to {_pct(a.get('terminal_roe'))} against a {_pct(a.get('cost_of_equity'))} cost of equity; "
                     f"the justified price-to-book is {v.get('justified_pb', 0):.2f}x vs. {v.get('market_pb') or 0:.2f}x in the market.")
    for flag in v.get("flags", [])[:3]:
        lines.append(f"- Note: {flag['message']}")
    return lines


def _expectations(ctx: dict[str, Any]) -> list[str]:
    e = ctx.get("expectations")
    if not e:
        return ["The reverse DCF is unavailable for this company."]
    lines = list(e.get("narrative", []))
    if e.get("odds") is not None:
        lines.append(f"Given the company's own historical variability, about **{_pct(e['odds'], 0)}** of simulated growth/margin "
                     "outcomes are worth more than today's price.")
    return lines


def _comps(ctx: dict[str, Any]) -> list[str]:
    comps, c, v = ctx.get("comps"), ctx["company"], ctx.get("intrinsic") or {}
    if not comps:
        return ["Trading comparables are unavailable (too few valid peers in the sector)."]
    ccy = c["currency"]
    lines = [f"On the peer median {comps['primary_label']} the shares are worth about **{_money(comps['implied_mid'], ccy, True)}** "
             f"(interquartile range {_money(comps['implied_low'], ccy, True)} to {_money(comps['implied_high'], ccy, True)}).",
             f"Peers: {', '.join(comps['peers'][:8])}."]
    if v.get("implied_share_price") and comps.get("implied_mid"):
        gap = v["implied_share_price"] / comps["implied_mid"] - 1
        lines.append(f"The intrinsic value is {_pct(abs(gap))} {'above' if gap > 0 else 'below'} the comps value: "
                     + ("the market prices peers more richly than your cash-flow assumptions justify." if gap < 0 else
                        "your cash-flow assumptions are more optimistic than peer pricing."))
    return lines


def _risk(ctx: dict[str, Any]) -> list[str]:
    r = ctx.get("risk") or {}
    lines = []
    if r.get("annualized_volatility") is not None:
        lines.append(f"- Realised volatility is {_pct(r['annualized_volatility'])} a year; a 1-in-20 bad day costs about "
                     f"{_pct(r.get('var_95_historical'))} (historical VaR) and the average loss beyond that is {_pct(r.get('es_95_historical'))}.")
    if r.get("evt_var_99") is not None:
        lines.append(f"- The fitted tail (EVT) puts the 1-in-100-day loss at {_pct(r['evt_var_99'])} (tail index {r.get('evt_xi', 0):.2f}).")
    if r.get("merton_pd") is not None:
        dd = "not meaningful (no debt)" if r.get("merton_dd") is None else f"{r['merton_dd']:.1f} standard deviations"
        lines.append(f"- Merton model: distance to default {dd}, 1-year risk-neutral default probability {_pct(r['merton_pd'], 2)}.")
    if r.get("regime"):
        lines.append(f"- The HMM places the stock in a **{r['regime']}** regime "
                     f"({'statistically supported' if r.get('regimes_supported') else 'regime structure not statistically supported'}).")
    for issue in (ctx.get("data_quality") or {}).get("warnings", [])[:2]:
        lines.append(f"- Data caveat: {issue}")
    return lines or ["Risk metrics are unavailable (insufficient price history)."]


def _lbo(ctx: dict[str, Any]) -> list[str]:
    lbo, ccy = ctx.get("lbo"), ctx["company"]["currency"]
    if not lbo:
        return ["An LBO is not applicable here (a bank/insurer, or no positive EBITDA)."]
    lines = [f"Buying at {lbo['entry_multiple']:.1f}x EBITDA with {lbo['entry_leverage']:.1f}x leverage and exiting at "
             f"{lbo['exit_multiple']:.1f}x gives a **{_pct(lbo['irr'])} IRR** ({lbo['moic']:.2f}x MOIC).",
             f"Value creation: EBITDA growth {_money(lbo['attribution']['ebitda_growth'], ccy)}, multiple change "
             f"{_money(lbo['attribution']['multiple_expansion'], ccy)}, deleveraging {_money(lbo['attribution']['deleveraging'], ccy)}, "
             f"fees {_money(lbo['attribution']['fees_and_leakage'], ccy)}."]
    lines += [f"- {m}" for m in lbo.get("flags", [])[:3]]
    return lines


def _mna(ctx: dict[str, Any]) -> list[str]:
    m = ctx.get("mna")
    if not m:
        return ["No acquirer is selected. Open the M&A page and choose one to model accretion/dilution."]
    ccy = m["currency"]
    lines = [f"{m['acquirer']} acquiring {m['target']} at {_money(m['offer_price'], ccy, True)} per share "
             f"({_money(m['purchase_price'], ccy)} equity value): year-1 EPS changes **{_pct(m['eps_change_pct'])}** "
             f"({_pct(m['eps_change_pct_run_rate'])} at run-rate)."]
    if m.get("break_even") is not None:
        lines.append(f"Break-even requires about {_money(m['break_even'], ccy)} of pre-tax synergies; target holders would own "
                     f"{_pct(m['ownership_target'])} of the combined company.")
    lines += [f"- {msg}" for msg in m.get("flags", [])[:3]]
    return lines


def _assumptions(ctx: dict[str, Any]) -> list[str]:
    lines = ["The assumptions that move value most in this model:"]
    v, a = ctx.get("intrinsic") or {}, ctx.get("assumptions") or {}
    if ctx.get("valuation_model") == "dcf":
        spread = (a.get("wacc") or 0) - (a.get("terminal_growth") or 0)
        lines.append(f"- **WACC and terminal growth**: the spread is {_pct(spread, 2)} and the terminal value is "
                     f"{_pct(v.get('terminal_share_of_ev'), 0)} of EV, so a 0.5-point change in either moves value materially.")
        lines.append(f"- **Revenue growth ({_pct(a.get('revenue_growth'))})** compounds for {a.get('projection_years')} years and sets the terminal base.")
        lines.append(f"- **Target margin ({_pct(a.get('ebitda_margin'))})** drives every year's cash flow.")
    else:
        lines.append("- **ROE vs. cost of equity**: value exists only to the extent ROE exceeds the cost of equity.")
        lines.append("- **Terminal ROE and growth** set the long-run excess return.")
    lines.append("The Valuation page has the two-way sensitivity grids; the Risk lab has the tornado chart.")
    return lines


def _wacc(ctx: dict[str, Any]) -> list[str]:
    w = ctx.get("wacc_build")
    if not w:
        return ["The discount-rate build is unavailable."]
    return [f"WACC of **{_pct(w['wacc'], 2)}**: cost of equity {_pct(w['cost_of_equity'], 2)} = risk-free {_pct(w['risk_free_rate'], 2)} + "
            f"beta {w['beta']:.2f} x ERP {_pct(w['equity_risk_premium'])}; beta source: {w['beta_source']}.",
            f"After-tax cost of debt {_pct(w['after_tax_cost_of_debt'], 2)} at a {_pct(w['weight_debt'], 0)} debt weight."]


def _case(ctx: dict[str, Any], bull: bool) -> list[str]:
    e, a = ctx.get("expectations") or {}, ctx.get("assumptions") or {}
    lines = [f"**{'Bull' if bull else 'Bear'} case** (framed with the model's own sensitivities, not a forecast):"]
    if ctx.get("valuation_model") == "dcf":
        if bull:
            lines.append(f"- Growth above {_pct(e.get('implied_growth'))} (what the price already assumes) or margins beyond "
                         f"{_pct(e.get('implied_margin'))} would make today's price look cheap.")
        else:
            lines.append(f"- If growth reverts toward the historical {_pct(e.get('historical_cagr'))} CAGR, value converges to your "
                         f"scenario of {_money((ctx.get('intrinsic') or {}).get('implied_share_price'), ctx['company']['currency'], True)}.")
        lines.append(f"- Each 0.5-point move in WACC (currently {_pct(a.get('wacc'), 2)}) shifts value noticeably; see the sensitivity grid.")
    lines += _risk(ctx)[:2] if not bull else []
    return lines


def offline_answer(message: str, ctx: dict[str, Any]) -> str:
    intent = detect_intent(message)
    builders = {
        "valuation": _valuation, "expectations": _expectations, "comps": _comps, "risk": _risk, "lbo": _lbo,
        "mna": _mna, "assumptions": _assumptions, "wacc": _wacc,
        "bull": lambda c: _case(c, True), "bear": lambda c: _case(c, False),
    }
    if intent == "overview":
        body = _valuation(ctx) + [""] + _expectations(ctx)[:1] + ["", "Ask about *what's priced in*, *comps*, *risks*, "
                                                                      "*the LBO*, *the M&A deal* or *which assumptions matter*."]
    else:
        body = builders[intent](ctx)
    return "\n".join(body)


def offline_memo(ctx: dict[str, Any]) -> str:
    c = ctx["company"]
    sections = [
        f"# Investment committee memo: {c['name']} ({c['ticker']})",
        f"*Prepared by ValuEngine's rule-based analyst from the computed models. Data: {c['source']} (FY ending {c['fiscal_period']}), "
        f"price {_money(c.get('price'), c['currency'], True)}.*",
        "## 1. Valuation", *_valuation(ctx),
        "## 2. What the market is pricing in", *_expectations(ctx),
        "## 3. Relative value", *_comps(ctx),
        "## 4. Transaction perspectives", *_lbo(ctx), "", *_mna(ctx),
        "## 5. Key risks", *_risk(ctx),
        "## 6. Assumptions to challenge", *_assumptions(ctx)[1:],
        "---",
        "*This memo is generated from model outputs and is not investment advice.*",
    ]
    return "\n\n".join(line for line in sections if line is not None)
