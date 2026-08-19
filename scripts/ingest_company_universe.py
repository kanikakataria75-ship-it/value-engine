"""CLI Script for Bulk Company Universe Ingestion.

Executes bulk ingestion of company fundamentals and daily price series into the
local SQLite store using a pluggable market data provider.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from mna_lbo_engine.modules.bulk_data_ingestor import BulkDataIngestor
from mna_lbo_engine.modules.market_data_provider import MockMarketDataProvider
from mna_lbo_engine.modules.yfinance_provider import YFinanceProvider
from mna_lbo_engine.modules.local_financial_store import LocalFinancialStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ValuEngine Bulk Company Universe Ingestor")
    parser.add_argument(
        "--universe",
        type=str,
        default=str(PROJECT_ROOT / "data" / "company_universe.csv"),
        help="Path to company universe CSV file.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit of companies to process.",
    )
    parser.add_argument(
        "--tickers",
        type=str,
        default=None,
        help="Comma-separated list of explicit tickers to ingest (e.g. AAPL,MSFT,RELIANCE.NSE).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Force overwrite existing records in SQLite database.",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="yfinance",
        choices=["yfinance", "mock"],
        help="Market data provider implementation to use (default: yfinance).",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Optional path to target SQLite database.",
    )
    return parser.parse_args()


def progress_logger(current: int, total: int, ticker: str, status: str) -> None:
    pct = (current / total) * 100
    badge = "[OK]" if status in {"SUCCESS", "SKIPPED_ALREADY_EXISTS"} else "[FAIL]"
    print(f"[{current:>3}/{total:>3} ({pct:>5.1f}%)] {badge:<6} {ticker:<15}: {status}")


def main() -> None:
    args = parse_args()
    print("=" * 72)
    print("VALUENGINE — BULK DATA INGESTION ENGINE")
    print("=" * 72)
    print(f"Universe File : {args.universe}")
    print(f"Provider      : {args.provider}")
    print(f"Overwrite     : {args.overwrite}")
    if args.limit:
        print(f"Batch Limit   : {args.limit}")
    if args.tickers:
        print(f"Tickers Filter: {args.tickers}")
    print("-" * 72)

    # Instantiate provider
    if args.provider == "mock":
        provider = MockMarketDataProvider()
    elif args.provider == "yfinance":
        provider = YFinanceProvider()
    else:
        raise ValueError(f"Unsupported provider: {args.provider}")

    store = LocalFinancialStore(db_path=args.db_path) if args.db_path else None
    ingestor = BulkDataIngestor(
        provider=provider,
        store=store,
        universe_csv=args.universe,
    )

    ticker_list = [t.strip() for t in args.tickers.split(",")] if args.tickers else None

    result = ingestor.ingest_universe(
        limit=args.limit,
        ticker_list=ticker_list,
        overwrite=args.overwrite,
        progress_callback=progress_logger,
    )

    print("=" * 72)
    print("INGESTION BATCH SUMMARY")
    print("=" * 72)
    print(f"Total Processed   : {result['total_processed']}")
    print(f"Successfully Added: {result['successful']}")
    print(f"Skipped (Resume)  : {result['skipped']}")
    print(f"Failed Validation : {result['failed']}")
    print(f"Success Rate      : {result['success_rate']}")
    print(f"DB Total Companies: {result['db_company_count']}")
    print("=" * 72)


if __name__ == "__main__":
    main()
