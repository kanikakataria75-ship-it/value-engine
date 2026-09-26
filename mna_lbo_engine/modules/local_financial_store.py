"""Local SQLite financial data store and repository layer.

Stores company fundamentals (latest fiscal year), annual fundamentals history, daily prices
and FX rates. Everything served from here is labelled LOCAL: the original provider and
retrieval time travel along in the provenance block, but local data is never reported as live.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from .common import to_float

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "financial_data.db"

FUNDAMENTAL_FIELDS = (
    "current_price", "market_cap", "shares_outstanding", "revenue", "ebitda", "ebit", "net_income",
    "eps", "operating_cash_flow", "capex", "d_and_a", "total_debt", "cash_and_equivalents",
    "book_equity", "total_assets", "total_liabilities", "beta",
)
HISTORY_FIELDS = ("revenue", "ebitda", "ebit", "net_income", "operating_cash_flow", "capex", "d_and_a")

CANONICAL_SECTORS = {
    "basic materials", "communication services", "consumer cyclical", "consumer defensive", "energy",
    "financial services", "healthcare", "industrials", "real estate", "technology", "utilities",
}
# Alpha Vantage reports SIC-office style sectors; map them onto the Yahoo/GICS-like taxonomy used locally.
SECTOR_ALIASES = {
    "technology": "Technology",
    "information technology": "Technology",
    "life sciences": "Healthcare",
    "health care": "Healthcare",
    "finance": "Financial Services",
    "financials": "Financial Services",
    "real estate & construction": "Real Estate",
    "energy & transportation": "Energy",
    "manufacturing": "Industrials",
    "trade & services": "Consumer Cyclical",
    "consumer discretionary": "Consumer Cyclical",
    "consumer staples": "Consumer Defensive",
    "materials": "Basic Materials",
    "communication": "Communication Services",
}


def normalize_sector(sector: Any) -> str | None:
    if sector is None:
        return None
    text = str(sector).strip()
    if not text:
        return None
    key = text.lower()
    if key in SECTOR_ALIASES:
        return SECTOR_ALIASES[key]
    if key in CANONICAL_SECTORS:
        return " ".join(part.capitalize() for part in key.split(" "))
    return text


class LocalFinancialStore:
    """SQLite repository. Each operation opens and closes its own connection (thread-safe)."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS company_fundamentals (
                    ticker TEXT PRIMARY KEY NOT NULL,
                    company_name TEXT, exchange TEXT, sector TEXT, industry TEXT,
                    currency TEXT DEFAULT 'USD',
                    current_price REAL, market_cap REAL, shares_outstanding REAL,
                    revenue REAL, ebitda REAL, ebit REAL, net_income REAL, eps REAL,
                    operating_cash_flow REAL, capex REAL, d_and_a REAL,
                    total_debt REAL, cash_and_equivalents REAL, book_equity REAL,
                    total_assets REAL, total_liabilities REAL, beta REAL,
                    period TEXT, retrieved_at TEXT, provenance_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_fundamentals_sector ON company_fundamentals(sector);

                CREATE TABLE IF NOT EXISTS daily_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL, high REAL, low REAL,
                    close REAL NOT NULL,
                    volume REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ticker, date) ON CONFLICT REPLACE,
                    FOREIGN KEY (ticker) REFERENCES company_fundamentals(ticker) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_daily_prices_ticker_date ON daily_prices(ticker, date DESC);
                CREATE INDEX IF NOT EXISTS idx_daily_prices_date ON daily_prices(date);

                CREATE TABLE IF NOT EXISTS fundamentals_history (
                    ticker TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    revenue REAL, ebitda REAL, ebit REAL, net_income REAL,
                    operating_cash_flow REAL, capex REAL, d_and_a REAL,
                    currency TEXT,
                    source TEXT,
                    PRIMARY KEY (ticker, period_end),
                    FOREIGN KEY (ticker) REFERENCES company_fundamentals(ticker) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS fx_rates (
                    pair TEXT NOT NULL,
                    date TEXT NOT NULL,
                    rate REAL NOT NULL,
                    source TEXT,
                    PRIMARY KEY (pair, date)
                );
                """
            )

    # ------------------------------------------------------------------ fundamentals
    def save_company(self, financials: dict[str, Any], preserve_classification: bool = False) -> None:
        """Insert or update a company snapshot.

        preserve_classification keeps an existing sector/industry (used when a live provider
        with a different taxonomy refreshes a company that is already classified locally).
        """
        ticker = str(financials.get("ticker", "")).strip().upper()
        if not ticker:
            raise ValueError("Cannot save company without a valid ticker.")

        provenance = financials.get("provenance") or {}
        if not isinstance(provenance, dict):
            provenance = {"source": str(provenance)}
        period = financials.get("period") or provenance.get("period_end") or provenance.get("period")
        retrieved_at = financials.get("retrieved_at") or provenance.get("retrieved_at") or ""

        sector = normalize_sector(financials.get("sector"))
        industry = financials.get("industry")
        if preserve_classification:
            existing = self.get_company(ticker, include_prices=False)
            if existing and existing.get("sector"):
                sector, industry = existing["sector"], existing.get("industry") or industry

        values = {field: to_float(financials.get(field)) for field in FUNDAMENTAL_FIELDS}
        with self._connect() as conn:
            conn.execute(
                f"""
                INSERT INTO company_fundamentals (
                    ticker, company_name, exchange, sector, industry, currency,
                    {", ".join(FUNDAMENTAL_FIELDS)}, period, retrieved_at, provenance_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, {", ".join("?" for _ in FUNDAMENTAL_FIELDS)}, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(ticker) DO UPDATE SET
                    company_name = excluded.company_name, exchange = excluded.exchange,
                    sector = excluded.sector, industry = excluded.industry, currency = excluded.currency,
                    {", ".join(f"{field} = excluded.{field}" for field in FUNDAMENTAL_FIELDS)},
                    period = excluded.period, retrieved_at = excluded.retrieved_at,
                    provenance_json = excluded.provenance_json, updated_at = CURRENT_TIMESTAMP
                """,
                (
                    ticker, financials.get("company_name"), financials.get("exchange"), sector, industry,
                    (financials.get("currency") or "USD").upper(),
                    *[values[field] for field in FUNDAMENTAL_FIELDS],
                    period, retrieved_at, json.dumps(provenance),
                ),
            )

        prices = financials.get("historical_prices")
        if isinstance(prices, list) and prices:
            self.save_daily_prices(ticker, prices)
        history = financials.get("fundamentals_history")
        if isinstance(history, list) and history:
            self.save_history(ticker, history)

    def update_fields(self, ticker: str, fields: dict[str, Any], provenance: dict[str, Any] | None = None) -> None:
        """Targeted update used by data-repair scripts."""
        allowed = set(FUNDAMENTAL_FIELDS) | {"company_name", "exchange", "sector", "industry", "currency", "period"}
        assignments, params = [], []
        for key, value in fields.items():
            if key not in allowed:
                raise ValueError(f"Field {key!r} cannot be updated.")
            assignments.append(f"{key} = ?")
            params.append(to_float(value) if key in FUNDAMENTAL_FIELDS else value)
        if provenance is not None:
            assignments.append("provenance_json = ?")
            params.append(json.dumps(provenance))
        if not assignments:
            return
        with self._connect() as conn:
            conn.execute(
                f"UPDATE company_fundamentals SET {', '.join(assignments)}, updated_at = CURRENT_TIMESTAMP WHERE ticker = ?",
                (*params, ticker.strip().upper()),
            )

    def get_company(self, ticker: str, include_prices: bool = True, price_limit: int | None = None) -> dict[str, Any] | None:
        symbol = str(ticker).strip().upper()
        if not symbol:
            return None
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM company_fundamentals WHERE ticker = ?", (symbol,)).fetchone()
        if row is None:
            return None
        result = self._row_to_company(row)
        result["historical_prices"] = self.get_daily_prices(symbol, limit=price_limit) if include_prices else []
        return result

    @staticmethod
    def _row_to_company(row: sqlite3.Row) -> dict[str, Any]:
        stored: dict[str, Any] = {}
        if row["provenance_json"]:
            try:
                stored = json.loads(row["provenance_json"]) or {}
            except (json.JSONDecodeError, TypeError):
                stored = {}
        origin = stored.get("provider") or stored.get("source_name") or stored.get("source") or "Unknown provider"
        provenance = {
            "source_type": "LOCAL",
            "source_name": "ValuEngine local store",
            "origin": str(origin).replace(" Bulk Ingest", "").replace(" (Cached)", ""),
            "retrieved_at": row["retrieved_at"] or stored.get("retrieved_at"),
            "period_end": row["period"],
            "period_type": "FY",
            "currency": row["currency"] or "USD",
            "derived_fields": stored.get("derived_fields", []),
            "repairs": stored.get("repairs", []),
            "notice": "Latest fiscal-year fundamentals from the local SQLite store.",
        }
        company: dict[str, Any] = {
            "ticker": row["ticker"],
            "company_name": row["company_name"] or row["ticker"],
            "exchange": row["exchange"],
            "sector": normalize_sector(row["sector"]),
            "industry": row["industry"],
            "currency": (row["currency"] or "USD").upper(),
            "period": row["period"],
            "retrieved_at": row["retrieved_at"],
            "provenance": provenance,
        }
        for field in FUNDAMENTAL_FIELDS:
            company[field] = row[field]
        return company

    def list_company_rows(self) -> list[dict[str, Any]]:
        """All fundamentals rows (no prices), for universe-level analytics."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM company_fundamentals ORDER BY ticker").fetchall()
        return [self._row_to_company(row) for row in rows]

    def list_companies(self, sector: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT ticker, company_name, exchange, sector, industry, currency, current_price, market_cap FROM company_fundamentals"
        params: list[Any] = []
        if sector:
            query += " WHERE sector = ?"
            params.append(sector)
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(query + " ORDER BY ticker ASC", params).fetchall()]

    def search_companies(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search by ticker, name or sector. Ordering uses USD-normalised market cap so ₹ and $ compare fairly."""
        q = str(query).strip()
        sql = "SELECT ticker, company_name, exchange, sector, industry, currency, current_price, market_cap FROM company_fundamentals"
        params: list[Any] = []
        if q:
            sql += " WHERE UPPER(ticker) LIKE UPPER(?) OR UPPER(company_name) LIKE UPPER(?) OR UPPER(sector) LIKE UPPER(?)"
            params = [f"%{q}%"] * 3
        with self._connect() as conn:
            rows = [dict(row) for row in conn.execute(sql, params).fetchall()]

        upper_q = q.upper()

        def rank(row: dict[str, Any]) -> int:
            if not q:
                return 0
            ticker = row["ticker"].upper()
            if ticker == upper_q or ticker.split(".")[0] == upper_q:
                return 0
            if ticker.startswith(upper_q):
                return 1
            if str(row["company_name"] or "").upper().startswith(upper_q):
                return 2
            return 3

        rates = self.latest_usd_rates()
        results = []
        for row in rows:
            rate = rates.get((row["currency"] or "USD").upper())
            cap = to_float(row["market_cap"])
            usd_cap = cap / rate if cap is not None and rate else None
            results.append({**row, "_rank": rank(row), "market_cap_usd": usd_cap})
        results.sort(key=lambda r: (r["_rank"], -(r["market_cap_usd"] or 0), r["ticker"]))
        return [self._search_display(row) for row in results[:limit]]

    @staticmethod
    def _search_display(row: dict[str, Any]) -> dict[str, Any]:
        ticker = row["ticker"]
        exchange = row["exchange"] or ""
        currency = (row["currency"] or "USD").upper()
        india = currency == "INR" or ticker.endswith((".NSE", ".BSE"))
        if india:
            exchange_display = "BSE" if ticker.endswith(".BSE") else "NSE"
        elif exchange in {"NMS", "NGS", "NCM", "NASDAQ", "NasdaqGS", "NasdaqGM"}:
            exchange_display = "NASDAQ"
        elif exchange in {"NYQ", "NYSE"}:
            exchange_display = "NYSE"
        else:
            exchange_display = exchange or "—"
        return {
            "ticker": ticker,
            "company_name": row["company_name"] or ticker,
            "exchange": exchange_display,
            "country": "India" if india else "USA",
            "sector": normalize_sector(row["sector"]) or "Unclassified",
            "industry": row["industry"] or "",
            "currency": currency,
            "current_price": row["current_price"],
            "market_cap": row["market_cap"],
            "market_cap_usd": row.get("market_cap_usd"),
        }

    def get_peer_candidates(self, ticker: str, sector: str | None) -> list[dict[str, Any]]:
        """Same-sector companies (excluding the target) with the fields needed for multiples."""
        symbol = str(ticker).strip().upper()
        if not sector:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM company_fundamentals WHERE UPPER(ticker) != ? AND sector = ?",
                (symbol, sector),
            ).fetchall()
        return [self._row_to_company(row) for row in rows]

    def delete_company(self, ticker: str) -> bool:
        symbol = str(ticker).strip().upper()
        if not symbol:
            return False
        with self._connect() as conn:
            return conn.execute("DELETE FROM company_fundamentals WHERE ticker = ?", (symbol,)).rowcount > 0

    def get_company_count(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM company_fundamentals").fetchone()[0])

    def get_stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            companies = conn.execute("SELECT COUNT(*) FROM company_fundamentals").fetchone()[0]
            by_currency = dict(conn.execute("SELECT currency, COUNT(*) FROM company_fundamentals GROUP BY currency").fetchall())
            prices, first_date, last_date = conn.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM daily_prices").fetchone()
            history_rows, history_tickers = conn.execute(
                "SELECT COUNT(*), COUNT(DISTINCT ticker) FROM fundamentals_history"
            ).fetchone()
            retrieved = conn.execute("SELECT MIN(retrieved_at), MAX(retrieved_at) FROM company_fundamentals").fetchone()
            updated = conn.execute("SELECT MAX(updated_at) FROM company_fundamentals").fetchone()[0]
        return {
            "company_count": int(companies),
            "companies_by_currency": by_currency,
            "price_rows": int(prices or 0),
            "price_start": first_date,
            "price_end": last_date,
            "history_rows": int(history_rows or 0),
            "history_companies": int(history_tickers or 0),
            "retrieved_from": retrieved[0],
            "retrieved_to": retrieved[1],
            "updated_at": updated,
        }

    def data_signature(self) -> tuple:
        """Cheap fingerprint used to invalidate in-memory analytics caches after data changes."""
        with self._connect() as conn:
            return tuple(conn.execute(
                "SELECT (SELECT COUNT(*) FROM company_fundamentals), (SELECT MAX(updated_at) FROM company_fundamentals),"
                " (SELECT COUNT(*) FROM daily_prices), (SELECT MAX(date) FROM daily_prices),"
                " (SELECT COUNT(*) FROM fundamentals_history), (SELECT COUNT(*) FROM fx_rates)"
            ).fetchone())

    # ------------------------------------------------------------------ prices
    def save_daily_prices(self, ticker: str, prices: list[dict[str, Any]]) -> int:
        symbol = str(ticker).strip().upper()
        records = []
        for p in prices or []:
            if not isinstance(p, dict):
                continue
            close = to_float(p.get("close"))
            if p.get("date") and close is not None:
                records.append((symbol, str(p["date"])[:10], to_float(p.get("open")), to_float(p.get("high")),
                                to_float(p.get("low")), close, to_float(p.get("volume"))))
        if not records:
            return 0
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO daily_prices (ticker, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, date) DO UPDATE SET
                    open = COALESCE(excluded.open, daily_prices.open), high = COALESCE(excluded.high, daily_prices.high),
                    low = COALESCE(excluded.low, daily_prices.low), close = excluded.close,
                    volume = COALESCE(excluded.volume, daily_prices.volume)
                """,
                records,
            )
        return len(records)

    def get_daily_prices(self, ticker: str, limit: int | None = None) -> list[dict[str, Any]]:
        symbol = str(ticker).strip().upper()
        if not symbol:
            return []
        query = "SELECT date, open, high, low, close, volume FROM daily_prices WHERE ticker = ? ORDER BY date DESC"
        params: list[Any] = [symbol]
        if limit is not None and limit > 0:
            query += " LIMIT ?"
            params.append(limit)
        with self._connect() as conn:
            rows = [dict(row) for row in conn.execute(query, params).fetchall()]
        rows.reverse()
        return rows

    def get_price_panel(self, tickers: list[str] | None = None) -> list[tuple[str, str, float]]:
        """(ticker, date, close) rows for many tickers, used to build factor and market indices."""
        query = "SELECT ticker, date, close FROM daily_prices"
        params: list[Any] = []
        if tickers:
            query += f" WHERE ticker IN ({', '.join('?' for _ in tickers)})"
            params = [t.upper() for t in tickers]
        with self._connect() as conn:
            return [(r[0], r[1], r[2]) for r in conn.execute(query + " ORDER BY date", params).fetchall()]

    # ------------------------------------------------------------------ history
    def save_history(self, ticker: str, rows: list[dict[str, Any]], source: str | None = None) -> int:
        symbol = str(ticker).strip().upper()
        records = []
        for row in rows:
            period_end = str(row.get("period_end") or "")[:10]
            if not period_end:
                continue
            records.append((symbol, period_end, *[to_float(row.get(field)) for field in HISTORY_FIELDS],
                            row.get("currency"), row.get("source") or source))
        if not records:
            return 0
        with self._connect() as conn:
            conn.executemany(
                f"""
                INSERT INTO fundamentals_history (ticker, period_end, {", ".join(HISTORY_FIELDS)}, currency, source)
                VALUES (?, ?, {", ".join("?" for _ in HISTORY_FIELDS)}, ?, ?)
                ON CONFLICT(ticker, period_end) DO UPDATE SET
                    {", ".join(f"{f} = excluded.{f}" for f in HISTORY_FIELDS)}, currency = excluded.currency, source = excluded.source
                """,
                records,
            )
        return len(records)

    def get_history(self, ticker: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM fundamentals_history WHERE ticker = ? ORDER BY period_end ASC", (ticker.strip().upper(),)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_all_history(self) -> dict[str, list[dict[str, Any]]]:
        """Every company's history in one query (for universe-level analytics)."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM fundamentals_history ORDER BY ticker, period_end").fetchall()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row["ticker"], []).append(dict(row))
        return grouped

    def tickers_with_history(self) -> set[str]:
        with self._connect() as conn:
            return {r[0] for r in conn.execute("SELECT DISTINCT ticker FROM fundamentals_history").fetchall()}

    # ------------------------------------------------------------------ bulk import / export
    TABLES = ("company_fundamentals", "daily_prices", "fundamentals_history", "fx_rates")

    def table_columns(self, table: str) -> list[str]:
        if table not in self.TABLES:
            raise ValueError(f"Unknown table {table!r}.")
        with self._connect() as conn:
            return [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]

    def iter_table(self, table: str, columns: list[str]) -> list[tuple]:
        if table not in self.TABLES:
            raise ValueError(f"Unknown table {table!r}.")
        with self._connect() as conn:
            return conn.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY {columns[0]}").fetchall()

    def bulk_insert(self, table: str, columns: list[str], rows: list[tuple]) -> int:
        if table not in self.TABLES:
            raise ValueError(f"Unknown table {table!r}.")
        with self._connect() as conn:
            conn.executemany(
                f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})", rows
            )
        return len(rows)

    # ------------------------------------------------------------------ FX
    def save_fx_rates(self, pair: str, rows: list[tuple[str, float]], source: str) -> int:
        records = [(pair.upper(), str(date)[:10], float(rate), source) for date, rate in rows if to_float(rate)]
        with self._connect() as conn:
            conn.executemany(
                "INSERT INTO fx_rates (pair, date, rate, source) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(pair, date) DO UPDATE SET rate = excluded.rate, source = excluded.source",
                records,
            )
        return len(records)

    def get_fx_rate(self, pair: str, on_or_before: str | None = None) -> dict[str, Any] | None:
        """Latest stored rate for a pair such as USDINR (INR per USD), optionally as of a date."""
        query = "SELECT pair, date, rate, source FROM fx_rates WHERE pair = ?"
        params: list[Any] = [pair.upper()]
        if on_or_before:
            query += " AND date <= ?"
            params.append(str(on_or_before)[:10])
        with self._connect() as conn:
            row = conn.execute(query + " ORDER BY date DESC LIMIT 1", params).fetchone()
        return dict(row) if row else None

    def latest_usd_rates(self) -> dict[str, float]:
        """{currency: units per USD} using the latest stored rate for each USDxxx pair (USD itself = 1)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT pair, rate FROM fx_rates f WHERE date = (SELECT MAX(date) FROM fx_rates WHERE pair = f.pair)"
            ).fetchall()
        rates = {"USD": 1.0}
        for pair, rate in rows:
            if str(pair).startswith("USD") and rate:
                rates[str(pair)[3:]] = float(rate)
        return rates

    def to_usd(self, amount: Any, currency: str | None) -> float | None:
        value = to_float(amount)
        if value is None:
            return None
        currency = (currency or "USD").upper()
        if currency == "USD":
            return value
        fx = self.get_fx_rate(f"USD{currency}")
        return value / fx["rate"] if fx else None


_default_store: LocalFinancialStore | None = None


def get_default_store() -> LocalFinancialStore:
    global _default_store
    if _default_store is None:
        _default_store = LocalFinancialStore()
    return _default_store


def set_default_store(store: LocalFinancialStore | None) -> None:
    """Swap the process-wide store (used by tests and the data bootstrap)."""
    global _default_store
    _default_store = store
