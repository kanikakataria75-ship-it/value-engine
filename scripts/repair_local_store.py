"""Idempotent repairs for records already in the local store.

  * canonical sector names (e.g. Alpha Vantage's "TECHNOLOGY" -> "Technology")
  * EBITDA rebuilt as EBIT + D&A where the stored EBITDA is below EBIT
  * reports records whose price/sales ratio suggests statements in a different currency than the
    price (re-ingest those with scripts/ingest_company_universe.py --tickers ... --overwrite)

Every change is recorded in the record's provenance ("repairs"). Run with --dry-run to preview.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mna_lbo_engine.modules.common import reconcile_ebitda  # noqa: E402
from mna_lbo_engine.modules.local_financial_store import LocalFinancialStore, normalize_sector  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair records in the local store")
    parser.add_argument("--db", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    store = LocalFinancialStore(args.db)

    changed, suspects = 0, []
    for company in store.list_company_rows():
        ticker = company["ticker"]
        updates, repairs = {}, []
        sector = normalize_sector(company.get("sector"))
        if sector and sector != company.get("sector"):
            updates["sector"] = sector
            repairs.append(f"sector normalised to {sector}")
        ebitda, derived = reconcile_ebitda(company.get("ebitda"), company.get("ebit"), company.get("d_and_a"))
        if derived and ebitda is not None:
            updates["ebitda"] = ebitda
            repairs.append("ebitda rebuilt as EBIT + D&A (reported EBITDA was below EBIT)")
        if company.get("market_cap") and company.get("revenue") and company["market_cap"] / company["revenue"] > 60:
            suspects.append(ticker)
        if updates:
            changed += 1
            provenance = dict(company.get("provenance") or {})
            stored = {k: v for k, v in provenance.items() if k not in {"source_type", "source_name", "notice"}}
            stored["provider"] = provenance.get("origin")
            stored["repairs"] = sorted(set((provenance.get("repairs") or []) + repairs))
            if "ebitda" in updates:
                stored["derived_fields"] = sorted(set((provenance.get("derived_fields") or []) + ["ebitda (EBIT + D&A)"]))
            print(f"{ticker:16s} {'; '.join(repairs)}")
            if not args.dry_run:
                store.update_fields(ticker, updates, provenance=stored)
    print(f"{changed} records {'would be ' if args.dry_run else ''}repaired.")
    if suspects:
        print("Possible statement-currency mismatch (re-ingest these):", ", ".join(suspects))


if __name__ == "__main__":
    main()
