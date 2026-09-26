"""Build data/financial_data.db from the committed snapshot (offline, a few seconds).

The API does this automatically when it starts with an empty database; this script is for doing
it explicitly, e.g. to rebuild after deleting the database.

Usage:  python scripts/bootstrap_data.py [--force]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mna_lbo_engine.modules.local_financial_store import DEFAULT_DB_PATH, LocalFinancialStore  # noqa: E402
from mna_lbo_engine.modules.snapshot import import_snapshot, snapshot_available  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the local database from data/snapshot/")
    parser.add_argument("--force", action="store_true", help="Delete an existing database first")
    args = parser.parse_args()
    if not snapshot_available():
        sys.exit("data/snapshot/ is incomplete; nothing to import.")
    if DEFAULT_DB_PATH.exists():
        if not args.force:
            sys.exit(f"{DEFAULT_DB_PATH} already exists. Use --force to rebuild it from the snapshot.")
        for suffix in ("", "-wal", "-shm"):
            Path(str(DEFAULT_DB_PATH) + suffix).unlink(missing_ok=True)
    counts = import_snapshot(LocalFinancialStore())
    print(f"Imported snapshot into {DEFAULT_DB_PATH}: {counts}")


if __name__ == "__main__":
    main()
