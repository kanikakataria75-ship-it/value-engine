"""Currency conversion backed by FX rates stored in the local database.

Rates are stored as USDxxx pairs (units of xxx per 1 USD). Every conversion returns the
rate, its date and its source so that converted figures stay auditable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .common import to_float


@dataclass(frozen=True)
class FxQuote:
    from_currency: str
    to_currency: str
    rate: float          # units of to_currency per 1 unit of from_currency
    date: str | None
    source: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class FxUnavailable(RuntimeError):
    pass


class FxConverter:
    def __init__(self, store: Any) -> None:
        self.store = store

    def _usd_rate(self, currency: str, as_of: str | None) -> tuple[float, str | None, str]:
        """Units of `currency` per 1 USD."""
        if currency == "USD":
            return 1.0, None, "identity"
        row = self.store.get_fx_rate(f"USD{currency}", on_or_before=as_of) if as_of else None
        row = row or self.store.get_fx_rate(f"USD{currency}")
        if not row or not to_float(row.get("rate")):
            raise FxUnavailable(f"No stored FX rate for USD/{currency}. Run scripts/update_fx.py.")
        return float(row["rate"]), row.get("date"), row.get("source") or "local fx table"

    def quote(self, from_currency: str | None, to_currency: str | None, as_of: str | None = None) -> FxQuote:
        src = (from_currency or "USD").upper()
        dst = (to_currency or "USD").upper()
        if src == dst:
            return FxQuote(src, dst, 1.0, None, "identity")
        src_per_usd, src_date, src_source = self._usd_rate(src, as_of)
        dst_per_usd, dst_date, dst_source = self._usd_rate(dst, as_of)
        date = max(d for d in (src_date, dst_date) if d) if (src_date or dst_date) else None
        source = src_source if src != "USD" else dst_source
        return FxQuote(src, dst, dst_per_usd / src_per_usd, date, source)

    def convert(self, amount: Any, from_currency: str | None, to_currency: str | None, as_of: str | None = None) -> float | None:
        value = to_float(amount)
        if value is None:
            return None
        return value * self.quote(from_currency, to_currency, as_of).rate


MONETARY_FIELDS = (
    "current_price", "market_cap", "revenue", "ebitda", "ebit", "net_income", "eps", "operating_cash_flow",
    "capex", "d_and_a", "total_debt", "cash_and_equivalents", "book_equity", "total_assets", "total_liabilities",
)


def convert_company(company: dict[str, Any], quote: FxQuote) -> dict[str, Any]:
    """Return a copy of a company record restated in quote.to_currency (share counts untouched)."""
    converted = dict(company)
    for field in MONETARY_FIELDS:
        value = to_float(company.get(field))
        converted[field] = value * quote.rate if value is not None else None
    converted["currency"] = quote.to_currency
    converted["historical_prices"] = []
    converted["fx_conversion"] = quote.as_dict()
    return converted
