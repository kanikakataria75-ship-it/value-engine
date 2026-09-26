"""Shared, dependency-free helpers for the financial engines."""
from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

INDIA_SUFFIXES = (".NSE", ".BSE", ".NS", ".BO")


def to_float(value: Any) -> float | None:
    """Convert provider/DB values to float; None, blanks, NaN and infinities become None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        if text in {"", "None", "null", "nan", "NaN", "-"}:
            return None
        value = text
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def num(data: Mapping[str, Any] | None, key: str) -> float | None:
    return to_float(data.get(key)) if data else None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def missing_fields(data: Mapping[str, Any], fields: Iterable[str]) -> list[str]:
    return [field for field in fields if num(data, field) is None]


def country_of(company: Mapping[str, Any]) -> str:
    ticker = str(company.get("ticker") or "").upper()
    currency = str(company.get("currency") or "").upper()
    if currency == "INR" or ticker.endswith(INDIA_SUFFIXES):
        return "India"
    return "United States"


def is_balance_sheet_financial(company: Mapping[str, Any]) -> bool:
    """Banks, insurers and lenders, whose value is driven by book equity and ROE rather than free cash flow.

    Fee-based financials (payment networks, exchanges, rating agencies, brokers, asset managers)
    are valued like any other operating company.
    """
    sector = str(company.get("sector") or "").lower()
    if "financial" not in sector:
        return False
    industry = str(company.get("industry") or "").lower()
    asset_intensity = safe_div(num(company, "total_assets"), num(company, "revenue"))
    if industry.startswith("banks") or (industry.startswith("insurance") and "broker" not in industry):
        return True
    if industry in {"mortgage finance", "financial conglomerates"}:
        return True
    if industry in {"insurance brokers", "financial data & stock exchanges"}:
        return False  # fee businesses; exchanges hold clearing collateral that inflates assets
    if industry == "asset management":
        return asset_intensity is not None and asset_intensity > 20  # holding companies / NBFCs
    # Credit services and capital markets: lenders and broker-dealers carry large balance sheets,
    # payment networks and depositories do not.
    return asset_intensity is not None and asset_intensity > 3.5


def reconcile_ebitda(reported: Any, ebit: Any, d_and_a: Any) -> tuple[float | None, bool]:
    """Operating EBITDA that is consistent with EBIT.

    Providers sometimes compute "EBITDA" from pre-tax income (including non-operating losses),
    which can leave it below operating income. EBITDA can never be below EBIT when D&A >= 0,
    so in that case, or when EBITDA is missing, it is rebuilt as EBIT + D&A.
    Returns (value, derived).
    """
    reported_value, ebit_value, da_value = to_float(reported), to_float(ebit), to_float(d_and_a)
    if ebit_value is not None and (reported_value is None or reported_value < ebit_value):
        return ebit_value + max(da_value or 0.0, 0.0), True
    return reported_value, False


def fmt_money(value: float, currency: str | None) -> str:
    """Compact amount for messages: $1.48B / $312.5M for dollars, lakh-crore / crore for rupees."""
    sign = "-" if value < 0 else ""
    amount = abs(value)
    if (currency or "USD").upper() == "INR":
        if amount >= 1e12:
            return f"{sign}₹{amount / 1e12:,.2f} L Cr"
        if amount >= 1e7:
            return f"{sign}₹{amount / 1e7:,.0f} Cr"
        return f"{sign}₹{amount:,.0f}"
    for scale, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if amount >= scale:
            return f"{sign}${amount / scale:,.2f}{suffix}"
    return f"{sign}${amount:,.0f}"


def flag(severity: str, module: str, code: str, message: str) -> dict[str, str]:
    """Structured diagnostic. severity: INVALID | REVIEW | INFO."""
    return {"severity": severity, "module": module, "code": code, "message": message}
