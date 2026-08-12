# Python vs Excel Reconciliation Report

## Discrepancies Found

### 1. LBO Sponsor Initial Equity
- **Python Calculation (`lbo_engine.py`)**: 
  `purchase_equity = entry_ev + target_net_debt`
  `sponsor_initial_equity = purchase_equity - total_debt_initial`
- **Excel Calculation (`excel_exporter.py`)**: 
  `=C6-C11` where C6 is Entry EV and C11 is Total Debt Tranches. This translates to `Sponsor Equity = Entry EV - Total Debt Funded`.
- **Resolution**: The Excel formula is mathematically correct. The Python engine is artificially inflating the Sponsor Equity by adding `target_net_debt`. The Python code must be updated to match the standard Uses of Funds (Uses = Entry EV, assuming no fees; Sponsor Equity = Uses - Debt). 

### 2. General Formula Consistency
- DCF formulas match exactly between Python and Excel (`=C26-C27` for Equity Value, etc.).
- M&A formulas match exactly between Python and Excel.
- LBO IRR matches (`=IRR(B37:G37)` vs `numpy_financial.irr`).

### 3. Missing Excel Features
- Excel does not currently output sensitivity matrices (Data Tables).
- Excel does not output Data Quality or Provenance warnings.
- Excel is missing a dedicated "Checks" sheet (Balance Sheet check, DCF check, etc.).

## Action Plan
- Fix the `lbo_engine.py` Sponsor Equity calculation.
- Add reconciliation unit tests to the CI pipeline to enforce Python `==` Excel.
