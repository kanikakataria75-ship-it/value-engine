"""Fetch daily USD FX history from Yahoo Finance into the local store.

Usage:  python scripts/update_fx.py [--currencies INR] [--period 2y]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mna_lbo_engine.modules.local_financial_store import LocalFinancialStore  # noqa: E402
from mna_lbo_engine.modules.yfinance_provider import YFinanceProvider  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Update FX rates (USDxxx pairs) in the local store")
    parser.add_argument("--currencies", default="INR", help="Comma-separated currencies quoted against USD")
    parser.add_argument("--period", default="2y", help="History window, e.g. 1y, 2y, 5y")
    parser.add_argument("--db", default=None, help="Path to the SQLite database (defaults to data/financial_data.db)")
    args = parser.parse_args()

    store = LocalFinancialStore(args.db)
    provider = YFinanceProvider()
    for currency in [c.strip().upper() for c in args.currencies.split(",") if c.strip()]:
        rows = provider.fx_history("USD", currency, period=args.period)
        saved = store.save_fx_rates(f"USD{currency}", rows, source="Yahoo Finance")
        latest = store.get_fx_rate(f"USD{currency}")
        print(f"USD{currency}: stored {saved} daily rates; latest {latest['rate']:.4f} on {latest['date']}" if latest
              else f"USD{currency}: no rates returned")


if __name__ == "__main__":
    main()
