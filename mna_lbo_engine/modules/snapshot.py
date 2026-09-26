"""Portable data snapshot: CSV files committed to the repository that rebuild the SQLite store offline.

The SQLite database itself is not versioned. `export_snapshot` writes the store to data/snapshot/
and `import_snapshot` rebuilds an empty store from it, so a fresh clone works without network access.
"""
from __future__ import annotations

import csv
import gzip
from pathlib import Path
from typing import Any

from .local_financial_store import PROJECT_ROOT, LocalFinancialStore

SNAPSHOT_DIR = PROJECT_ROOT / "data" / "snapshot"
FILES = {
    "company_fundamentals": "fundamentals.csv",
    "fundamentals_history": "history.csv",
    "fx_rates": "fx.csv",
    "daily_prices": "prices.csv.gz",
}
SKIP_COLUMNS = {"id", "created_at", "updated_at"}


def _open(path: Path, mode: str):
    if path.suffix == ".gz":
        return gzip.open(path, mode + "t", encoding="utf-8", newline="")
    return open(path, mode, encoding="utf-8", newline="")


def _convert(value: str) -> Any:
    if value == "":
        return None
    try:
        return float(value) if any(ch in value for ch in ".eE") or value.lstrip("-").isdigit() else value
    except ValueError:
        return value


def _format(table: str, column: str, value: Any) -> Any:
    """Serialise a value; prices are rounded (4 dp, whole-share volume) to keep the snapshot small."""
    if value is None:
        return ""
    if not isinstance(value, float):
        return value
    if table == "daily_prices":
        return f"{value:.0f}" if column == "volume" else f"{value:.4f}"
    return repr(value)


def snapshot_available(directory: Path = SNAPSHOT_DIR) -> bool:
    return all((directory / name).exists() for name in FILES.values())


def export_snapshot(store: LocalFinancialStore, directory: Path = SNAPSHOT_DIR) -> dict[str, int]:
    directory.mkdir(parents=True, exist_ok=True)
    counts = {}
    for table, name in FILES.items():
        columns = [c for c in store.table_columns(table) if c not in SKIP_COLUMNS]
        rows = store.iter_table(table, columns)
        with _open(directory / name, "w") as handle:
            writer = csv.writer(handle)
            writer.writerow(columns)
            for row in rows:
                writer.writerow([_format(table, column, value) for column, value in zip(columns, row)])
        counts[table] = len(rows)
    return counts


def import_snapshot(store: LocalFinancialStore, directory: Path = SNAPSHOT_DIR) -> dict[str, int]:
    counts = {}
    text_columns = {"ticker", "company_name", "exchange", "sector", "industry", "currency", "period", "retrieved_at",
                    "provenance_json", "date", "period_end", "source", "pair"}
    for table, name in FILES.items():
        with _open(directory / name, "r") as handle:
            reader = csv.reader(handle)
            columns = next(reader)
            rows = [tuple((None if v == "" else v) if col in text_columns else _convert(v) for col, v in zip(columns, row))
                    for row in reader]
        counts[table] = store.bulk_insert(table, columns, rows)
    return counts
