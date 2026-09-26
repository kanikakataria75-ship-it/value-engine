"""Yahoo Finance market data provider.

Adapts yfinance to the MarketDataProvider interface for US and Indian (.NSE / .BSE) equities.
Two rules matter for data integrity:
  * statements are restated from the reporting currency (`financialCurrency`) into the trading
    currency, so price-based and statement-based figures are always comparable;
  * missing values stay missing (None). Defaults are decided, and flagged, by the ingestor.
"""
from __future__ import annotations

import logging
from typing import Any

import yfinance as yf

from .common import reconcile_ebitda, to_float
from .market_data_provider import MarketDataProvider

logger = logging.getLogger(__name__)

_EBIT_KEYS = ["Operating Income", "EBIT"]
_EBIT_FALLBACK_KEYS = ["Pretax Income"]
CAPEX_KEYS = ["Capital Expenditure", "Capital Expenditure Reported", "Purchase Of PPE", "Net PPE Purchase And Sale",
              "Purchase Of Real Estate", "Net Investment Properties Purchase And Sale"]  # REITs report property purchases


ANCHOR_KEYS = {
    "income": ["Total Revenue", "Operating Revenue"],
    "balance": ["Total Assets"],
    "cashflow": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
}


def _anchor_column(df: Any, anchor: list[str]) -> Any:
    """Most recent period whose anchor line is reported.

    A company changing its fiscal year can leave the newest column empty; all fields of a statement
    are then read from the same (latest complete) period rather than mixing periods.
    """
    for column in df.columns:
        if any(key in df.index and to_float(df.loc[key, column]) is not None for key in anchor):
            return column
    return df.columns[0]


def _latest(df: Any, keys: list[str], anchor: list[str] | None = None) -> tuple[str | None, float | None]:
    if df is None or getattr(df, "empty", True):
        return None, None
    column = _anchor_column(df, anchor) if anchor else df.columns[0]
    period = str(column.date() if hasattr(column, "date") else column)[:10]
    for key in keys:
        if key in df.index:
            value = to_float(df.loc[key, column])
            if value is not None:
                return period, value
    return period, None


def _value(df: Any, column: Any, keys: list[str]) -> float | None:
    for key in keys:
        if key in df.index:
            value = to_float(df.loc[key, column])
            if value is not None:
                return value
    return None


class YFinanceProvider(MarketDataProvider):
    def __init__(self, name: str = "YahooFinance") -> None:
        self._name = name
        self._tickers: dict[str, yf.Ticker] = {}
        self._infos: dict[str, dict[str, Any]] = {}
        self._fx: dict[tuple[str, str], tuple[float, str]] = {}

    @property
    def provider_name(self) -> str:
        return self._name

    @staticmethod
    def to_provider_ticker(ticker: str) -> str:
        symbol = str(ticker).strip().upper()
        if symbol.endswith(".NSE"):
            return symbol[:-4] + ".NS"
        if symbol.endswith(".BSE"):
            return symbol[:-4] + ".BO"
        if "." in symbol and not symbol.endswith((".NS", ".BO", ".L", ".TO")):
            return symbol.replace(".", "-")  # BRK.B -> BRK-B
        return symbol

    def _ticker(self, ticker: str) -> yf.Ticker:
        symbol = self.to_provider_ticker(ticker)
        if symbol not in self._tickers:
            self._tickers[symbol] = yf.Ticker(symbol)
        return self._tickers[symbol]

    def _info(self, ticker: str) -> dict[str, Any]:
        symbol = self.to_provider_ticker(ticker)
        if symbol not in self._infos:
            self._infos[symbol] = self._ticker(ticker).info or {}
        return self._infos[symbol]

    # ------------------------------------------------------------------ FX
    def fx_rate(self, from_currency: str, to_currency: str) -> tuple[float, str]:
        """Units of to_currency per 1 from_currency, with the quote date."""
        key = (from_currency.upper(), to_currency.upper())
        if key[0] == key[1]:
            return 1.0, ""
        if key not in self._fx:
            history = yf.Ticker(f"{key[0]}{key[1]}=X").history(period="5d", interval="1d")
            if history is None or history.empty:
                raise RuntimeError(f"FX rate {key[0]}/{key[1]} unavailable from Yahoo Finance")
            self._fx[key] = (float(history["Close"].iloc[-1]), str(history.index[-1].date()))
        return self._fx[key]

    def fx_history(self, from_currency: str, to_currency: str, period: str = "2y") -> list[tuple[str, float]]:
        history = yf.Ticker(f"{from_currency.upper()}{to_currency.upper()}=X").history(period=period, interval="1d")
        if history is None or history.empty:
            return []
        return [(str(idx.date()), float(close)) for idx, close in history["Close"].items() if to_float(close)]

    def statement_conversion(self, ticker: str) -> dict[str, Any] | None:
        """FX used to restate statements into the trading currency, or None when no restatement is needed."""
        info = self._info(ticker)
        reporting, trading = info.get("financialCurrency"), info.get("currency")
        if not reporting or not trading or reporting.upper() == trading.upper():
            return None
        rate, date = self.fx_rate(reporting, trading)
        return {"from": reporting.upper(), "to": trading.upper(), "rate": rate, "date": date, "source": "Yahoo Finance FX"}

    def _multiplier(self, ticker: str) -> float:
        conversion = self.statement_conversion(ticker)
        return conversion["rate"] if conversion else 1.0

    # ------------------------------------------------------------------ interface
    def get_company_profile(self, ticker: str) -> dict[str, Any]:
        info = self._info(ticker)
        return {
            "name": info.get("longName") or info.get("shortName"),
            "exchange": info.get("exchange"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "currency": info.get("currency"),
            "financial_currency": info.get("financialCurrency"),
            "shares_outstanding": to_float(info.get("sharesOutstanding")) or to_float(info.get("impliedSharesOutstanding")),
            "beta": to_float(info.get("beta")),
            "market_cap": to_float(info.get("marketCap")),
        }

    def get_quote(self, ticker: str) -> dict[str, Any]:
        t = self._ticker(ticker)
        price = None
        try:
            price = to_float(t.fast_info.last_price)
        except Exception:  # fast_info raises for some delisted symbols
            price = None
        if price is None:
            info = self._info(ticker)
            price = to_float(info.get("currentPrice")) or to_float(info.get("regularMarketPrice"))
        return {"price": price}

    def get_income_statement(self, ticker: str) -> dict[str, Any]:
        df = self._ticker(ticker).income_stmt
        m = self._multiplier(ticker)
        period, revenue = _latest(df, ["Total Revenue", "Operating Revenue"], ANCHOR_KEYS["income"])
        _, ebit = _latest(df, _EBIT_KEYS, ANCHOR_KEYS["income"])
        ebit_source = "Operating Income"
        if ebit is None:
            _, ebit = _latest(df, _EBIT_FALLBACK_KEYS, ANCHOR_KEYS["income"])
            ebit_source = "Pretax Income (no operating income reported)" if ebit is not None else None
        _, ebitda = _latest(df, ["EBITDA", "Normalized EBITDA"], ANCHOR_KEYS["income"])
        _, net_income = _latest(df, ["Net Income", "Net Income Common Stockholders"], ANCHOR_KEYS["income"])
        _, eps = _latest(df, ["Diluted EPS", "Basic EPS"], ANCHOR_KEYS["income"])
        _, dep = _latest(df, ["Reconciled Depreciation", "Depreciation And Amortization"], ANCHOR_KEYS["income"])
        scale = lambda v: v * m if v is not None else None  # noqa: E731
        return {
            "period": period, "revenue": scale(revenue), "ebitda": scale(ebitda), "ebit": scale(ebit),
            "ebit_source": ebit_source, "net_income": scale(net_income), "eps": scale(eps), "depreciation": scale(dep),
        }

    def get_balance_sheet(self, ticker: str) -> dict[str, Any]:
        df = self._ticker(ticker).balance_sheet
        m = self._multiplier(ticker)
        period, total_debt = _latest(df, ["Total Debt"], ANCHOR_KEYS["balance"])
        _, short_debt = _latest(df, ["Current Debt", "Current Debt And Capital Lease Obligation"], ANCHOR_KEYS["balance"])
        _, long_debt = _latest(df, ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"], ANCHOR_KEYS["balance"])
        if total_debt is None and (short_debt is not None or long_debt is not None):
            total_debt = (short_debt or 0.0) + (long_debt or 0.0)
        _, cash = _latest(df, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"], ANCHOR_KEYS["balance"])
        _, equity = _latest(df, ["Stockholders Equity", "Common Stock Equity"], ANCHOR_KEYS["balance"])
        _, assets = _latest(df, ["Total Assets"], ANCHOR_KEYS["balance"])
        _, liabilities = _latest(df, ["Total Liabilities Net Minority Interest", "Total Liabilities"], ANCHOR_KEYS["balance"])
        scale = lambda v: v * m if v is not None else None  # noqa: E731
        return {
            "period": period, "total_debt": scale(total_debt), "short_term_debt": scale(short_debt),
            "long_term_debt": scale(long_debt), "cash_and_equivalents": scale(cash), "book_equity": scale(equity),
            "total_assets": scale(assets), "total_liabilities": scale(liabilities),
        }

    def get_cash_flow(self, ticker: str) -> dict[str, Any]:
        df = self._ticker(ticker).cashflow
        m = self._multiplier(ticker)
        period, ocf = _latest(df, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"], ANCHOR_KEYS["cashflow"])
        _, capex = _latest(df, CAPEX_KEYS, ANCHOR_KEYS["cashflow"])
        _, da = _latest(df, ["Depreciation And Amortization", "Reconciled Depreciation"], ANCHOR_KEYS["cashflow"])
        return {
            "period": period,
            "operating_cash_flow": ocf * m if ocf is not None else None,
            "capex": abs(capex) * m if capex is not None else None,
            "depreciation_amortization": da * m if da is not None else None,
        }

    def get_historical_prices(self, ticker: str, limit: int = 250) -> list[dict[str, Any]]:
        df = self._ticker(ticker).history(period="1y", interval="1d", auto_adjust=True)
        if df is None or df.empty:
            return []
        rows = []
        for idx, row in df.iterrows():
            close = to_float(row.get("Close"))
            if close is not None:
                rows.append({
                    "date": str(idx.date()), "open": to_float(row.get("Open")), "high": to_float(row.get("High")),
                    "low": to_float(row.get("Low")), "close": close, "volume": to_float(row.get("Volume")),
                })
        return rows[-limit:] if limit else rows

    def get_annual_history(self, ticker: str, years: int = 5) -> list[dict[str, Any]]:
        """Annual fundamentals (oldest first), restated into the trading currency."""
        t = self._ticker(ticker)
        income, cashflow = t.income_stmt, t.cashflow
        if income is None or income.empty:
            return []
        m = self._multiplier(ticker)
        trading_currency = (self._info(ticker).get("currency") or "").upper() or None
        rows = []
        for column in list(income.columns)[:years]:
            period_end = str(column.date() if hasattr(column, "date") else column)[:10]
            revenue = _value(income, column, ["Total Revenue", "Operating Revenue"])
            if revenue is None:
                continue
            ebit = _value(income, column, _EBIT_KEYS) or _value(income, column, _EBIT_FALLBACK_KEYS)
            da = _value(income, column, ["Reconciled Depreciation", "Depreciation And Amortization"])
            capex = ocf = None
            if cashflow is not None and not cashflow.empty and column in cashflow.columns:
                capex = _value(cashflow, column, CAPEX_KEYS)
                ocf = _value(cashflow, column, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"])
                da = da if da is not None else _value(cashflow, column, ["Depreciation And Amortization"])
            ebitda, _ = reconcile_ebitda(_value(income, column, ["EBITDA", "Normalized EBITDA"]), ebit, da)
            scale = lambda v: v * m if v is not None else None  # noqa: E731
            rows.append({
                "period_end": period_end, "revenue": scale(revenue), "ebitda": scale(ebitda), "ebit": scale(ebit),
                "net_income": scale(_value(income, column, ["Net Income", "Net Income Common Stockholders"])),
                "operating_cash_flow": scale(ocf), "capex": scale(abs(capex)) if capex is not None else None,
                "d_and_a": scale(da), "currency": trading_currency, "source": self._name,
            })
        rows.sort(key=lambda r: r["period_end"])
        return rows
