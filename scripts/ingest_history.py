"""Fetch multi-year annual fundamentals for every company already in the local store.

History powers the baseline assumptions (historical growth and margins), the Expectations Lab
and the company financials view.

Usage:  python scripts/ingest_history.py [--tickers AAPL,MSFT] [--overwrite] [--sleep 0.4]
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mna_lbo_engine.modules.local_financial_store import LocalFinancialStore  # noqa: E402
from mna_lbo_engine.modules.yfinance_provider import YFinanceProvider  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest annual fundamentals history")
    parser.add_argument("--tickers", default="", help="Comma-separated tickers (default: every company in the store)")
    parser.add_argument("--overwrite", action="store_true", help="Re-fetch companies that already have history")
    parser.add_argument("--sleep", type=float, default=0.4, help="Pause between companies (seconds)")
    parser.add_argument("--db", default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    store = LocalFinancialStore(args.db)
    provider = YFinanceProvider()
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()] or [r["ticker"] for r in store.list_companies()]
    done = set() if args.overwrite else store.tickers_with_history()
    todo = [t for t in tickers if t not in done]
    print(f"{len(todo)} companies to fetch ({len(tickers) - len(todo)} already have history)")

    ok, failed = 0, []
    for index, ticker in enumerate(todo, start=1):
        for attempt in range(3):
            try:
                rows = provider.get_annual_history(ticker)
                saved = store.save_history(ticker, rows)
                ok += 1 if saved else 0
                if not saved:
                    failed.append((ticker, "no annual statements returned"))
                break
            except Exception as exc:  # network / provider errors: back off and retry
                if attempt == 2:
                    failed.append((ticker, f"{type(exc).__name__}: {exc}"))
                else:
                    time.sleep(2.0 * (attempt + 1))
        if index % 25 == 0 or index == len(todo):
            print(f"  {index}/{len(todo)} processed, {ok} with history, {len(failed)} failed", flush=True)
        time.sleep(args.sleep)

    for ticker, reason in failed:
        print(f"  FAILED {ticker}: {reason}")
    print(f"Done: {ok} companies with history, {len(failed)} failures.")


if __name__ == "__main__":
    main()
