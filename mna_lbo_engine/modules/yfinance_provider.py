"""Yahoo Finance market data provider implementation.

Adapts yfinance library to the ValuEngine MarketDataProvider interface,
supporting both US equities and Indian (.NSE / .BSE) equities.
"""
from __future__ import annotations

import logging
from typing import Any
import yfinance as yf

from .market_data_provider import MarketDataProvider

logger = logging.getLogger(__name__)


def _to_float(val: Any) -> float | None:
    if val is None or val == "" or val == "None":
        return None
    try:
        f = float(val)
        return None if (f != f) else f  # filter NaN
    except (ValueError, TypeError):
        return None


def _get_latest_statement_value(df: Any, candidate_keys: list[str]) -> tuple[Any, float | None]:
    """Extract value from latest column of financial dataframe matching candidate keys."""
    if df is None or df.empty:
        return None, None
    latest_col = df.columns[0]
    period = str(latest_col.date() if hasattr(latest_col, "date") else latest_col)
    for key in candidate_keys:
        if key in df.index:
            val = _to_float(df.loc[key, latest_col])
            if val is not None:
                return period, val
    return period, None


class YFinanceProvider(MarketDataProvider):
    """Production market data provider adapter using Yahoo Finance."""

    def __init__(self, name: str = "YahooFinance") -> None:
        self._name = name

    @property
    def provider_name(self) -> str:
        return self._name

    @staticmethod
    def _to_provider_ticker(ticker: str) -> str:
        """Map ValuEngine ticker conventions to Yahoo Finance format."""
        symbol = str(ticker).strip().upper()
        if symbol.endswith(".NSE"):
            return symbol[:-4] + ".NS"
        if symbol.endswith(".BSE"):
            return symbol[:-4] + ".BO"
        # Convert BRK.B to BRK-B if needed
        if "." in symbol and not symbol.endswith((".NS", ".BO", ".L", ".TO")):
            return symbol.replace(".", "-")
        return symbol

    def _get_ticker_obj(self, ticker: str) -> yf.Ticker:
        provider_symbol = self._to_provider_ticker(ticker)
        return yf.Ticker(provider_symbol)

    def get_company_profile(self, ticker: str) -> dict[str, Any]:
        t = self._get_ticker_obj(ticker)
        info = t.info or {}

        name = info.get("shortName") or info.get("longName") or f"{ticker} Corp"
        exchange = info.get("exchange") or "UNKNOWN"
        sector = info.get("sector") or "UNKNOWN"
        industry = info.get("industry") or "UNKNOWN"
        currency = info.get("currency") or "USD"

        shares = _to_float(info.get("sharesOutstanding")) or _to_float(info.get("impliedSharesOutstanding"))
        beta = _to_float(info.get("beta"))
        if beta is None:
            beta = 1.0  # Default market beta if absent

        market_cap = _to_float(info.get("marketCap"))

        return {
            "name": name,
            "exchange": exchange,
            "sector": sector,
            "industry": industry,
            "currency": currency,
            "shares_outstanding": shares,
            "beta": beta,
            "market_cap": market_cap,
        }

    def get_quote(self, ticker: str) -> dict[str, Any]:
        t = self._get_ticker_obj(ticker)
        info = t.info or {}
        fast = getattr(t, "fast_info", None)

        price = None
        if fast is not None:
            try:
                price = _to_float(fast.last_price)
            except Exception:
                pass

        if price is None:
            price = _to_float(info.get("currentPrice")) or _to_float(info.get("regularMarketPrice"))

        volume = None
        if fast is not None:
            try:
                volume = _to_float(fast.last_volume)
            except Exception:
                pass
        if volume is None:
            volume = _to_float(info.get("regularMarketVolume")) or 0.0

        return {
            "price": price,
            "volume": volume,
        }

    def get_income_statement(self, ticker: str) -> dict[str, Any]:
        t = self._get_ticker_obj(ticker)
        df = t.financials

        period, revenue = _get_latest_statement_value(df, ["Total Revenue", "Operating Revenue"])
        _, ebit = _get_latest_statement_value(df, ["Operating Income", "EBIT", "Pretax Income", "Net Income Continuous Operations"])
        _, ebitda = _get_latest_statement_value(df, ["EBITDA", "Normalized EBITDA"])
        _, net_income = _get_latest_statement_value(df, ["Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations"])
        _, eps = _get_latest_statement_value(df, ["Diluted EPS", "Basic EPS"])
        _, dep = _get_latest_statement_value(df, ["Reconciled Depreciation", "Depreciation And Amortization", "Depreciation Amortization Depletion"])

        # Fallbacks for Banking / Financial institutions if Operating Income is omitted in GICS
        if ebit is None and net_income is not None:
            ebit = net_income

        return {
            "period": period or "LTM",
            "revenue": revenue,
            "ebitda": ebitda,
            "ebit": ebit,
            "net_income": net_income,
            "eps": eps,
            "depreciation": dep,
        }

    def get_balance_sheet(self, ticker: str) -> dict[str, Any]:
        t = self._get_ticker_obj(ticker)
        df = t.balance_sheet

        period, total_debt = _get_latest_statement_value(df, ["Total Debt"])
        _, short_debt = _get_latest_statement_value(df, ["Current Debt", "Current Debt And Capital Lease Obligation", "Commercial Paper"])
        _, long_debt = _get_latest_statement_value(df, ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"])
        if total_debt is None and (short_debt is not None or long_debt is not None):
            total_debt = (short_debt or 0.0) + (long_debt or 0.0)

        _, cash = _get_latest_statement_value(df, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments", "Other Short Term Investments"])
        _, equity = _get_latest_statement_value(df, ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"])
        _, assets = _get_latest_statement_value(df, ["Total Assets"])
        _, liab = _get_latest_statement_value(df, ["Total Liabilities Net Minority Interest", "Total Liabilities"])

        return {
            "period": period or "LTM",
            "total_debt": total_debt if total_debt is not None else 0.0,
            "short_term_debt": short_debt,
            "long_term_debt": long_debt,
            "cash_and_equivalents": cash if cash is not None else 0.0,
            "book_equity": equity,
            "total_assets": assets,
            "total_liabilities": liab,
        }

    def get_cash_flow(self, ticker: str) -> dict[str, Any]:
        t = self._get_ticker_obj(ticker)
        df = t.cashflow

        period, ocf = _get_latest_statement_value(df, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"])
        _, capex = _get_latest_statement_value(df, ["Capital Expenditure", "Capital Expenditure Reported"])
        _, da = _get_latest_statement_value(df, ["Depreciation And Amortization", "Reconciled Depreciation", "Depreciation Amortization Depletion"])

        # Default minimal capex for pure financial institutions if 0
        if capex is None:
            capex = 0.0

        return {
            "period": period or "LTM",
            "operating_cash_flow": ocf,
            "capex": abs(capex) if capex is not None else 0.0,
            "depreciation_amortization": da,
        }

    def get_historical_prices(self, ticker: str, limit: int = 250) -> list[dict[str, Any]]:
        t = self._get_ticker_obj(ticker)
        # Fetch 1 year of daily history to guarantee 200+ trading days
        df = t.history(period="1y", interval="1d", auto_adjust=True)
        if df is None or df.empty:
            return []

        rows: list[dict[str, Any]] = []
        for idx, row in df.iterrows():
            date_str = str(idx.date() if hasattr(idx, "date") else idx).split(" ")[0]
            close = _to_float(row.get("Close"))
            if close is not None:
                rows.append({
                    "date": date_str,
                    "open": _to_float(row.get("Open")),
                    "high": _to_float(row.get("High")),
                    "low": _to_float(row.get("Low")),
                    "close": close,
                    "volume": _to_float(row.get("Volume")),
                })

        return rows[-limit:] if limit and len(rows) > limit else rows
