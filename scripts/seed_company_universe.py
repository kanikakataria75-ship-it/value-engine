"""Seed / Validate Master Company Universe for ValuEngine Local Database.

Validates company_universe.csv schema, duplicate tickers, and displays
breakdowns by country, exchange, sector, and priority tiers.
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = PROJECT_ROOT / "data" / "company_universe.csv"

REQUIRED_COLUMNS = [
    "ticker",
    "company_name",
    "exchange",
    "country",
    "currency",
    "sector",
    "industry",
    "priority",
]


def load_and_validate_universe(csv_path: Path = CSV_PATH) -> list[dict[str, str]]:
    """Load company universe CSV, validate schema, and detect duplicates."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Universe file not found at: {csv_path}")

    records: list[dict[str, str]] = []
    seen_tickers: set[str] = set()
    duplicates: list[str] = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []

        # Validate required columns
        missing_cols = [col for col in REQUIRED_COLUMNS if col not in header]
        if missing_cols:
            raise ValueError(f"Missing required columns in CSV: {missing_cols}. Found: {header}")

        for line_num, row in enumerate(reader, start=2):
            ticker = (row.get("ticker") or "").strip().upper()
            if not ticker:
                raise ValueError(f"Line {line_num}: Empty ticker found.")

            if ticker in seen_tickers:
                duplicates.append(ticker)
            seen_tickers.add(ticker)

            # Check that essential fields are not empty
            for col in REQUIRED_COLUMNS:
                if not (row.get(col) or "").strip():
                    raise ValueError(f"Line {line_num} ({ticker}): Column '{col}' is empty.")

            records.append({col: (row.get(col) or "").strip() for col in REQUIRED_COLUMNS})

    if duplicates:
        raise ValueError(f"Duplicate tickers detected ({len(duplicates)}): {duplicates}")

    return records


def display_universe_summary(records: list[dict[str, str]]) -> None:
    """Print high-level statistics and grouped breakdowns."""
    total = len(records)
    print("=" * 72)
    print("VALUENGINE — MASTER COMPANY UNIVERSE REGISTRY")
    print("=" * 72)
    print(f"Total Companies Registered: {total}")
    print("-" * 72)

    # Breakdown by Country & Exchange
    country_counts = Counter(r["country"] for r in records)
    exchange_counts = Counter(r["exchange"] for r in records)
    priority_counts = Counter(r["priority"] for r in records)

    print("\n[ Country Breakdown ]")
    for country, count in country_counts.most_common():
        pct = (count / total) * 100
        print(f"  • {country:<15}: {count:>3} ({pct:>5.1f}%)")

    print("\n[ Exchange Breakdown ]")
    for exchange, count in exchange_counts.most_common():
        pct = (count / total) * 100
        print(f"  • {exchange:<15}: {count:>3} ({pct:>5.1f}%)")

    print("\n[ Priority Tier Breakdown ]")
    for priority, count in priority_counts.most_common():
        pct = (count / total) * 100
        print(f"  • {priority:<15}: {count:>3} ({pct:>5.1f}%)")

    # Sector Breakdown (Overall + By Country)
    sector_counts = Counter(r["sector"] for r in records)
    by_country_sector: dict[str, Counter] = defaultdict(Counter)
    for r in records:
        by_country_sector[r["country"]][r["sector"]] += 1

    print("\n[ Sector Breakdown ]")
    print(f"  {'Sector':<28} | {'US':<5} | {'India':<5} | {'Total':<6} | {'% Universe':<10}")
    print("  " + "-" * 62)
    for sector, count in sorted(sector_counts.items(), key=lambda x: -x[1]):
        us_c = by_country_sector["USA"][sector]
        in_c = by_country_sector["India"][sector]
        pct = (count / total) * 100
        print(f"  {sector:<28} | {us_c:>5} | {in_c:>5} | {count:>6} | {pct:>9.1f}%")

    print("=" * 72)
    print("Status: VALID — 0 duplicates, 100% schema compliance.")
    print("=" * 72)


def main() -> None:
    try:
        records = load_and_validate_universe()
        display_universe_summary(records)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
