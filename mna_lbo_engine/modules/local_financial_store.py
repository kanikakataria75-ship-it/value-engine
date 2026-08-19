"""Local SQLite financial data store and repository layer.

Provides local storage and retrieval for company fundamentals and daily prices,
matching the normalized ValuEngine schema produced by normalize_alpha_vantage().
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "financial_data.db"


class LocalFinancialStore:
    """Thread-safe SQLite repository for company fundamentals and historical prices."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        self._ensure_db_dir()
        self.init_db()

    def _ensure_db_dir(self) -> None:
        if self.db_path != Path(":memory:"):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def close(self) -> None:
        """Explicitly close resources if needed."""
        pass

    def init_db(self) -> None:
        """Create database tables and indexes if they do not exist."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS company_fundamentals (
                    ticker TEXT PRIMARY KEY NOT NULL,
                    company_name TEXT,
                    exchange TEXT,
                    sector TEXT,
                    industry TEXT,
                    currency TEXT DEFAULT 'USD',
                    current_price REAL,
                    market_cap REAL,
                    shares_outstanding REAL,
                    revenue REAL,
                    ebitda REAL,
                    ebit REAL,
                    net_income REAL,
                    eps REAL,
                    operating_cash_flow REAL,
                    capex REAL,
                    d_and_a REAL,
                    total_debt REAL,
                    cash_and_equivalents REAL,
                    book_equity REAL,
                    total_assets REAL,
                    total_liabilities REAL,
                    beta REAL,
                    period TEXT,
                    retrieved_at TEXT,
                    provenance_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_fundamentals_sector 
                ON company_fundamentals(sector);

                CREATE TABLE IF NOT EXISTS daily_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL NOT NULL,
                    volume REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ticker, date) ON CONFLICT REPLACE,
                    FOREIGN KEY (ticker) REFERENCES company_fundamentals(ticker) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_daily_prices_ticker_date 
                ON daily_prices(ticker, date DESC);

                CREATE INDEX IF NOT EXISTS idx_daily_prices_date 
                ON daily_prices(date);
            """)
            conn.commit()

    def save_company(self, financials: dict[str, Any]) -> None:
        """Insert or update a company fundamentals snapshot."""
        ticker = str(financials.get("ticker", "")).strip().upper()
        if not ticker:
            raise ValueError("Cannot save company without a valid ticker.")

        provenance_data = financials.get("provenance", {})
        if not isinstance(provenance_data, dict):
            provenance_data = {"source": str(provenance_data)}

        period = financials.get("period") or provenance_data.get("period", "LTM")
        retrieved_at = financials.get("retrieved_at") or provenance_data.get("retrieved_at", "")

        provenance_json = json.dumps(provenance_data)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO company_fundamentals (
                    ticker, company_name, exchange, sector, industry, currency,
                    current_price, market_cap, shares_outstanding, revenue, ebitda,
                    ebit, net_income, eps, operating_cash_flow, capex, d_and_a,
                    total_debt, cash_and_equivalents, book_equity, total_assets,
                    total_liabilities, beta, period, retrieved_at, provenance_json,
                    updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT(ticker) DO UPDATE SET
                    company_name = excluded.company_name,
                    exchange = excluded.exchange,
                    sector = excluded.sector,
                    industry = excluded.industry,
                    currency = excluded.currency,
                    current_price = excluded.current_price,
                    market_cap = excluded.market_cap,
                    shares_outstanding = excluded.shares_outstanding,
                    revenue = excluded.revenue,
                    ebitda = excluded.ebitda,
                    ebit = excluded.ebit,
                    net_income = excluded.net_income,
                    eps = excluded.eps,
                    operating_cash_flow = excluded.operating_cash_flow,
                    capex = excluded.capex,
                    d_and_a = excluded.d_and_a,
                    total_debt = excluded.total_debt,
                    cash_and_equivalents = excluded.cash_and_equivalents,
                    book_equity = excluded.book_equity,
                    total_assets = excluded.total_assets,
                    total_liabilities = excluded.total_liabilities,
                    beta = excluded.beta,
                    period = excluded.period,
                    retrieved_at = excluded.retrieved_at,
                    provenance_json = excluded.provenance_json,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (
                    ticker,
                    financials.get("company_name"),
                    financials.get("exchange"),
                    financials.get("sector"),
                    financials.get("industry"),
                    financials.get("currency", "USD"),
                    financials.get("current_price"),
                    financials.get("market_cap"),
                    financials.get("shares_outstanding"),
                    financials.get("revenue"),
                    financials.get("ebitda"),
                    financials.get("ebit"),
                    financials.get("net_income"),
                    financials.get("eps"),
                    financials.get("operating_cash_flow"),
                    financials.get("capex"),
                    financials.get("d_and_a"),
                    financials.get("total_debt"),
                    financials.get("cash_and_equivalents"),
                    financials.get("book_equity"),
                    financials.get("total_assets"),
                    financials.get("total_liabilities"),
                    financials.get("beta"),
                    period,
                    retrieved_at,
                    provenance_json,
                ),
            )
            conn.commit()

        # If historical prices are packaged with fundamentals, save them as well
        prices = financials.get("historical_prices")
        if isinstance(prices, list) and prices:
            self.save_daily_prices(ticker, prices)

    def get_company(self, ticker: str, include_prices: bool = True, price_limit: int | None = None) -> dict[str, Any] | None:
        """Retrieve the normalized company fundamentals dictionary."""
        symbol = str(ticker).strip().upper()
        if not symbol:
            return None

        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM company_fundamentals WHERE ticker = ?",
                (symbol,),
            )
            row = cursor.fetchone()
            if row is None:
                return None

            provenance = {}
            if row["provenance_json"]:
                try:
                    provenance = json.loads(row["provenance_json"])
                except (json.JSONDecodeError, TypeError):
                    provenance = {"source": "LOCAL_DB"}

            # Ensure provenance metadata matches store reality
            provenance.setdefault("source", "LOCAL_DB")
            provenance.setdefault("provenance", "LIVE")
            provenance.setdefault("source_type", "LOCAL_DB")
            provenance.setdefault("source_name", "ValuEngine Local Store")
            provenance.setdefault("period", row["period"] or "LTM")
            provenance.setdefault("currency", row["currency"] or "USD")

            result: dict[str, Any] = {
                "ticker": row["ticker"],
                "company_name": row["company_name"],
                "exchange": row["exchange"],
                "sector": row["sector"],
                "industry": row["industry"],
                "currency": row["currency"],
                "current_price": row["current_price"],
                "market_cap": row["market_cap"],
                "shares_outstanding": row["shares_outstanding"],
                "revenue": row["revenue"],
                "ebitda": row["ebitda"],
                "ebit": row["ebit"],
                "net_income": row["net_income"],
                "eps": row["eps"],
                "operating_cash_flow": row["operating_cash_flow"],
                "capex": row["capex"],
                "d_and_a": row["d_and_a"],
                "total_debt": row["total_debt"],
                "cash_and_equivalents": row["cash_and_equivalents"],
                "book_equity": row["book_equity"],
                "total_assets": row["total_assets"],
                "total_liabilities": row["total_liabilities"],
                "beta": row["beta"],
                "historical_prices": [],
                "provenance": provenance,
                "_provenance": provenance.get("provenance", "LIVE"),
            }

            if include_prices:
                result["historical_prices"] = self.get_daily_prices(symbol, limit=price_limit)

            return result

    def save_daily_prices(self, ticker: str, prices: list[dict[str, Any]]) -> int:
        """Insert or replace daily historical prices for a given company."""
        symbol = str(ticker).strip().upper()
        if not symbol or not prices:
            return 0

        valid_records = []
        for p in prices:
            if not isinstance(p, dict):
                continue
            date_val = p.get("date")
            close_val = p.get("close")
            if date_val and close_val is not None:
                valid_records.append((
                    symbol,
                    str(date_val),
                    p.get("open"),
                    p.get("high"),
                    p.get("low"),
                    float(close_val),
                    p.get("volume"),
                ))

        if not valid_records:
            return 0

        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO daily_prices (
                    ticker, date, open, high, low, close, volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, date) DO UPDATE SET
                    open = COALESCE(excluded.open, daily_prices.open),
                    high = COALESCE(excluded.high, daily_prices.high),
                    low = COALESCE(excluded.low, daily_prices.low),
                    close = excluded.close,
                    volume = COALESCE(excluded.volume, daily_prices.volume);
                """,
                valid_records,
            )
            conn.commit()
            return len(valid_records)

    def get_daily_prices(self, ticker: str, limit: int | None = None) -> list[dict[str, Any]]:
        """Retrieve historical daily prices ordered chronologically (or reverse if limited)."""
        symbol = str(ticker).strip().upper()
        if not symbol:
            return []

        query = "SELECT date, open, high, low, close, volume FROM daily_prices WHERE ticker = ? ORDER BY date ASC"
        params: list[Any] = [symbol]

        if limit is not None and limit > 0:
            query = "SELECT date, open, high, low, close, volume FROM daily_prices WHERE ticker = ? ORDER BY date DESC LIMIT ?"
            params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            records = [
                {
                    "date": row["date"],
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"],
                }
                for row in rows
            ]

            if limit is not None and limit > 0:
                records.reverse()  # Return in ascending chronological order

            return records

    def list_companies(self, sector: str | None = None) -> list[dict[str, Any]]:
        """List all stored company summaries, optionally filtered by sector."""
        query = "SELECT ticker, company_name, exchange, sector, industry, currency, current_price, market_cap FROM company_fundamentals"
        params: list[Any] = []
        if sector:
            query += " WHERE sector = ?"
            params.append(sector)
        query += " ORDER BY ticker ASC"

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def search_companies(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Lightweight search by ticker, company_name, or sector."""
        q = str(query).strip()
        if not q:
            sql = """
                SELECT ticker, company_name, exchange, sector, industry, currency, current_price, market_cap 
                FROM company_fundamentals 
                ORDER BY market_cap DESC NULLS LAST, ticker ASC 
                LIMIT ?
            """
            params: list[Any] = [limit]
        else:
            term = f"%{q}%"
            sql = """
                SELECT ticker, company_name, exchange, sector, industry, currency, current_price, market_cap,
                       CASE 
                           WHEN UPPER(ticker) = UPPER(?) THEN 0
                           WHEN UPPER(ticker) LIKE UPPER(?) THEN 1
                           WHEN UPPER(company_name) LIKE UPPER(?) THEN 2
                           ELSE 3
                       END as rank
                FROM company_fundamentals 
                WHERE UPPER(ticker) LIKE UPPER(?) 
                   OR UPPER(company_name) LIKE UPPER(?) 
                   OR UPPER(sector) LIKE UPPER(?)
                ORDER BY rank ASC, market_cap DESC NULLS LAST, ticker ASC 
                LIMIT ?
            """
            params = [q, f"{q}%", f"{q}%", term, term, term, limit]

        with self._get_connection() as conn:
            cursor = conn.execute(sql, params)
            results = []
            for row in cursor.fetchall():
                ticker_val = row["ticker"]
                exchange_val = row["exchange"] or "UNKNOWN"
                currency_val = row["currency"] or "USD"
                
                if ticker_val.endswith(".NSE") or ticker_val.endswith(".BSE") or exchange_val in {"NSE", "BSE", "NSI", "BSI"} or currency_val == "INR":
                    country = "India"
                    exchange_display = "NSE" if ticker_val.endswith(".NSE") else ("BSE" if ticker_val.endswith(".BSE") else exchange_val)
                else:
                    country = "USA"
                    exchange_display = "NASDAQ" if exchange_val in {"NMS", "NGS", "NCM", "NASDAQ"} else ("NYSE" if exchange_val in {"NYQ", "NYSE"} else exchange_val)

                results.append({
                    "ticker": ticker_val,
                    "company_name": row["company_name"] or ticker_val,
                    "exchange": exchange_display,
                    "country": country,
                    "sector": row["sector"] or "General",
                    "industry": row["industry"] or "",
                    "currency": currency_val,
                    "current_price": row["current_price"],
                    "market_cap": row["market_cap"],
                })
            return results

    def get_peers(self, ticker: str, sector: str | None = None, limit: int = 15) -> list[dict[str, Any]]:
        """Retrieve peer companies for trading comps from the local SQLite store."""
        symbol = str(ticker).strip().upper()
        with self._get_connection() as conn:
            if sector:
                cursor = conn.execute(
                    """
                    SELECT ticker, company_name, exchange, sector, industry, currency,
                           current_price, market_cap, shares_outstanding, revenue, ebitda,
                           ebit, net_income, total_debt, cash_and_equivalents
                    FROM company_fundamentals 
                    WHERE UPPER(ticker) != UPPER(?) AND sector = ? AND ebitda IS NOT NULL AND revenue IS NOT NULL
                    ORDER BY market_cap DESC NULLS LAST
                    LIMIT ?
                    """,
                    (symbol, sector, limit),
                )
                peers = [dict(row) for row in cursor.fetchall()]
                if len(peers) >= 2:
                    return peers

            cursor = conn.execute(
                """
                SELECT ticker, company_name, exchange, sector, industry, currency,
                       current_price, market_cap, shares_outstanding, revenue, ebitda,
                       ebit, net_income, total_debt, cash_and_equivalents
                FROM company_fundamentals 
                WHERE UPPER(ticker) != UPPER(?) AND ebitda IS NOT NULL AND revenue IS NOT NULL
                ORDER BY market_cap DESC NULLS LAST
                LIMIT ?
                """,
                (symbol, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_company(self, ticker: str) -> bool:
        """Delete a company and cascade delete its daily prices."""
        symbol = str(ticker).strip().upper()
        if not symbol:
            return False

        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM company_fundamentals WHERE ticker = ?", (symbol,))
            conn.commit()
            return cursor.rowcount > 0

    def get_company_count(self) -> int:
        """Return the number of stored companies."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM company_fundamentals")
            return cursor.fetchone()[0]


# Module-level convenience functions
_default_store: LocalFinancialStore | None = None


def get_default_store() -> LocalFinancialStore:
    global _default_store
    if _default_store is None:
        _default_store = LocalFinancialStore()
    return _default_store


def save_company(financials: dict[str, Any], store: LocalFinancialStore | None = None) -> None:
    """Convenience function to save company fundamentals."""
    (store or get_default_store()).save_company(financials)


def get_company(ticker: str, include_prices: bool = True, store: LocalFinancialStore | None = None) -> dict[str, Any] | None:
    """Convenience function to retrieve company fundamentals."""
    return (store or get_default_store()).get_company(ticker, include_prices=include_prices)


def save_daily_prices(ticker: str, prices: list[dict[str, Any]], store: LocalFinancialStore | None = None) -> int:
    """Convenience function to save historical prices."""
    return (store or get_default_store()).save_daily_prices(ticker, prices)


def get_daily_prices(ticker: str, limit: int | None = None, store: LocalFinancialStore | None = None) -> list[dict[str, Any]]:
    """Convenience function to get daily historical prices."""
    return (store or get_default_store()).get_daily_prices(ticker, limit=limit)


def search_companies(query: str, limit: int = 20, store: LocalFinancialStore | None = None) -> list[dict[str, Any]]:
    """Convenience function to search companies."""
    return (store or get_default_store()).search_companies(query, limit=limit)


def get_peers(ticker: str, sector: str | None = None, limit: int = 15, store: LocalFinancialStore | None = None) -> list[dict[str, Any]]:
    """Convenience function to get peer companies."""
    return (store or get_default_store()).get_peers(ticker, sector=sector, limit=limit)
