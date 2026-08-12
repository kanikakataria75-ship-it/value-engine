# Data Integrity Report

## Current State
The application relies on `modules/data_loader.py` to fetch data from `yfinance`. 

## Identified Issues
1. **Blind Fallbacks (Violation of Rule #8)**:
   - If a ticker is not found or the API fails, the application silently returns a "synthetic" dictionary (e.g., $10B Revenue, $2B Debt) or predefined presets (AAPL, MSFT, NVDA).
   - There is no UI indication that the data is fake, leading to high risk of presenting false financial models.
2. **Data Provenance Missing (Violation of Rule #6)**:
   - The outputs do not track where a number came from (Live, Cached, User Input, Default, Fallback).
3. **Data Quality Engine Missing (Violation of Rule #7)**:
   - The application does not rigorously test financial relationships. For example, if `Total Debt = 0` but `Interest Expense > 0`, or if `Market Cap` deviates wildly from `Price * Shares`, it does not warn the user.
4. **Time Period Ambiguity**:
   - yfinance may mix TTM income statement data with latest-quarter balance sheet data without disclosing the "As of" date to the user.

## Required V2 Architecture
- **Provenance Tags**: Every financial dictionary must include a `provenance` metadata object (e.g., `revenue_source: 'live'`, `revenue_period: 'FY2023'`, `revenue_date: '2026-08-11'`).
- **Strict Error States**: If `yfinance` fails, the UI must show a clear `DATA FETCH FAILED` error state. The user must *explicitly* choose to load demo data.
- **Data Quality Dashboard**: Implement a validation step that checks basic accounting identities and flags anomalies to the user before running the DCF/M&A/LBO engines.
