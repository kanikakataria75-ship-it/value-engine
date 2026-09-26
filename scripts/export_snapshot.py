"""Write the local store to data/snapshot/ (CSV files committed to the repository).

Usage:  python scripts/export_snapshot.py
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mna_lbo_engine.modules.local_financial_store import LocalFinancialStore  # noqa: E402
from mna_lbo_engine.modules.snapshot import SNAPSHOT_DIR, export_snapshot  # noqa: E402

if __name__ == "__main__":
    counts = export_snapshot(LocalFinancialStore())
    print(f"Snapshot written to {SNAPSHOT_DIR}: {counts}")
