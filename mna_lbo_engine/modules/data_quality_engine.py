"""Data quality engine.

Validates accounting identities and data completeness for a company record and returns
structured findings. Severity levels:
  ERROR   - the record cannot support valuation (e.g. no revenue or share count)
  WARNING - usable, but a number should be reviewed before relying on it
  INFO    - context the analyst should know (derived fields, staleness, definitions)
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .common import is_balance_sheet_financial, num, safe_div

CORE_FIELDS = ("current_price", "shares_outstanding", "market_cap", "revenue")
OPERATING_FIELDS = ("ebitda", "ebit", "net_income", "capex", "d_and_a", "total_debt", "cash_and_equivalents")
BALANCE_FIELDS = ("book_equity", "total_assets", "total_liabilities")
OPTIONAL_FIELDS = ("eps", "operating_cash_flow", "beta")
ALL_FIELDS = CORE_FIELDS + OPERATING_FIELDS + BALANCE_FIELDS + OPTIONAL_FIELDS

MODEL_DEPENDENCIES = {
    "capex": "DCF", "d_and_a": "DCF", "total_debt": "DCF, LBO, Merton", "cash_and_equivalents": "DCF",
    "ebitda": "LBO, comps", "net_income": "M&A, P/E", "book_equity": "ROIC, P/B, excess-return model",
}


def _issue(severity: str, rule: str, message: str, field: str | None = None) -> dict[str, Any]:
    return {"severity": severity, "rule": rule, "field": field, "message": message}


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def run_data_quality_checks(company: dict[str, Any], as_of: date | None = None) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    as_of = as_of or date.today()
    financial = is_balance_sheet_financial(company)

    for field in CORE_FIELDS:
        value = num(company, field)
        if value is None:
            issues.append(_issue("ERROR", "MISSING_CORE_FIELD", f"{field} is missing; valuation is not possible.", field))
        elif value <= 0:
            issues.append(_issue("ERROR", "NON_POSITIVE_CORE_FIELD", f"{field} must be positive (got {value:,.2f}).", field))

    for field in OPERATING_FIELDS + BALANCE_FIELDS:
        if num(company, field) is None:
            affected = MODEL_DEPENDENCIES.get(field)
            severity = "INFO" if financial and field in {"capex", "d_and_a", "ebitda"} else "WARNING"
            suffix = f" Affects: {affected}." if affected else ""
            issues.append(_issue(severity, "MISSING_FIELD", f"{field} is not reported.{suffix}", field))

    for field in OPTIONAL_FIELDS:
        if num(company, field) is None:
            issues.append(_issue("INFO", "MISSING_OPTIONAL_FIELD", f"{field} is not reported.", field))

    for field in ("total_debt", "cash_and_equivalents"):
        value = num(company, field)
        if value is not None and value < 0:
            issues.append(_issue("ERROR", "NEGATIVE_BALANCE", f"{field} cannot be negative ({value:,.0f}).", field))

    revenue, ebitda, ebit = num(company, "revenue"), num(company, "ebitda"), num(company, "ebit")
    if ebitda is not None and ebit is not None and ebit > ebitda * 1.0001 and ebitda > 0:
        issues.append(_issue("WARNING", "EBIT_EXCEEDS_EBITDA",
                             "EBIT exceeds EBITDA, which is impossible with non-negative D&A. EBITDA should be rebuilt as EBIT + D&A.",
                             "ebitda"))
    if revenue and ebitda is not None and ebitda > revenue and not financial:
        issues.append(_issue("WARNING", "EBITDA_EXCEEDS_REVENUE",
                             f"EBITDA ({ebitda / revenue:.0%} of revenue) exceeds revenue; check the revenue definition.", "ebitda"))

    price, shares, market_cap = num(company, "current_price"), num(company, "shares_outstanding"), num(company, "market_cap")
    if price and shares and market_cap:
        implied = price * shares
        gap = abs(market_cap - implied) / implied
        if gap > 0.10:
            issues.append(_issue("WARNING", "MARKET_CAP_MISMATCH",
                                 f"Reported market cap deviates {gap:.0%} from price x shares (share classes or stale share count).",
                                 "market_cap"))

    price_to_sales = safe_div(market_cap, revenue)
    pe = safe_div(market_cap, num(company, "net_income"))
    if price_to_sales and price_to_sales > 60 and (pe is None or pe > 300 or pe < 0):
        issues.append(_issue("WARNING", "CURRENCY_MISMATCH_SUSPECTED",
                             f"Price/sales of {price_to_sales:,.0f}x suggests statements and price are in different currencies.",
                             "revenue"))

    assets, liabilities, equity = num(company, "total_assets"), num(company, "total_liabilities"), num(company, "book_equity")
    if assets and liabilities is not None and equity is not None:
        gap = abs(assets - (liabilities + equity)) / assets
        if gap > 0.05:
            issues.append(_issue("WARNING", "BALANCE_SHEET_IDENTITY",
                                 f"Assets differ from liabilities + equity by {gap:.1%} (usually minority interest; check the source).",
                                 "total_assets"))
        else:
            issues.append(_issue("INFO", "BALANCE_SHEET_IDENTITY_OK",
                                 f"Assets = liabilities + equity within {gap:.2%}.", "total_assets"))

    if equity is not None and equity <= 0:
        issues.append(_issue("WARNING", "NEGATIVE_BOOK_EQUITY",
                             "Book equity is negative (often buybacks); ROIC, P/B and ROE are not meaningful.", "book_equity"))
    net_income = num(company, "net_income")
    if net_income is not None and net_income <= 0:
        issues.append(_issue("INFO", "LOSS_MAKING", "Net income is negative; P/E multiples are not meaningful.", "net_income"))

    beta = num(company, "beta")
    if (company.get("currency") or "USD").upper() != "USD":
        issues.append(_issue("INFO", "PROVIDER_BETA_NOT_USED",
                             "The provider beta is measured against the S&P 500; CAPM uses a beta regressed on the local market index.",
                             "beta"))
    elif beta is not None and (beta <= 0.1 or beta > 3.0):
        issues.append(_issue("WARNING", "BETA_OUT_OF_RANGE",
                             f"Provider beta {beta:.2f} is implausible for CAPM; the regression beta from price history is used instead.",
                             "beta"))

    period_end = _parse_date(company.get("period"))
    if period_end and (as_of - period_end).days > 460:
        issues.append(_issue("WARNING", "STALE_FUNDAMENTALS",
                             f"Latest fiscal year ended {period_end.isoformat()} ({(as_of - period_end).days} days ago).", "period"))
    retrieved = _parse_date(company.get("retrieved_at"))
    if retrieved and (as_of - retrieved).days > 45:
        issues.append(_issue("INFO", "SNAPSHOT_AGE",
                             f"Data snapshot retrieved {retrieved.isoformat()} ({(as_of - retrieved).days} days ago).", "retrieved_at"))

    prices = company.get("historical_prices")
    if isinstance(prices, list) and prices and len(prices) < 200:
        issues.append(_issue("WARNING", "SHORT_PRICE_HISTORY",
                             f"Only {len(prices)} daily prices; risk models need at least 200.", "historical_prices"))

    derived = (company.get("provenance") or {}).get("derived_fields") or []
    if derived:
        issues.append(_issue("INFO", "DERIVED_FIELDS", f"Derived rather than reported: {', '.join(derived)}.", None))
    if financial:
        issues.append(_issue("INFO", "BALANCE_SHEET_FINANCIAL",
                             "Bank/insurer/lender: valued with an excess-return (ROE vs. cost of equity) model instead of a cash-flow DCF.",
                             None))
    return issues


def summarize_quality(company: dict[str, Any], issues: list[dict[str, Any]]) -> dict[str, Any]:
    """Completeness and a transparent quality score computed from the findings."""
    present = [field for field in ALL_FIELDS if num(company, field) is not None]
    counts = {level: sum(1 for i in issues if i["severity"] == level) for level in ("ERROR", "WARNING", "INFO")}
    score = max(0, 100 - 40 * counts["ERROR"] - 8 * counts["WARNING"])
    return {
        "fields_present": len(present),
        "fields_total": len(ALL_FIELDS),
        "completeness": len(present) / len(ALL_FIELDS),
        "missing_fields": [field for field in ALL_FIELDS if field not in present],
        "counts": counts,
        "score": score,
        "status": "INVALID" if counts["ERROR"] else ("REVIEW_REQUIRED" if counts["WARNING"] else "VALID"),
        "price_records": len(company.get("historical_prices") or []),
    }
