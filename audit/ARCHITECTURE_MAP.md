# Current Architecture Map

## Overview
The application is a Python-based financial modeling platform using Streamlit for the UI, Pandas/NumPy for calculations, and OpenPyXL for Excel model generation. It fetches data via `yfinance`.

## Directory Structure
```
mna_lbo_engine/
├── app.py                      # Streamlit entry point (currently ~34KB, monolithic UI)
├── config.py                   # Global defaults, tax rates, presets, UI styling
├── requirements.txt            # Dependencies
└── modules/
    ├── data_loader.py          # yfinance data fetching and parsing
    ├── dcf_engine.py           # DCF, CAPM, WACC, intrinsic valuation
    ├── ma_engine.py            # M&A accretion/dilution mechanics
    ├── lbo_engine.py           # LBO simulator, debt waterfall, IRR
    └── excel_exporter.py       # OpenPyXL engine for .xlsx generation
```

## Data Flow
1. **Data Ingestion**: `app.py` -> `data_loader.py` fetches from `yfinance`. If data is missing or fails, it silently falls back to synthetic or preset data.
2. **Valuation Engine**: `app.py` calls `dcf_engine.py` using historical financials + assumptions to output a DCF valuation.
3. **M&A Engine**: `app.py` calls `ma_engine.py` using two companies' financials to calculate Pro-Forma EPS and Accretion/Dilution.
4. **LBO Engine**: `app.py` calls `lbo_engine.py` to calculate entry EV, sponsor equity, 5-year debt waterfall, and IRR.
5. **Export**: `app.py` passes the results dictionaries to `excel_exporter.py`, which generates `M_and_A_LBO_Model.xlsx`.

## Weaknesses & Required V2 Changes
- **Monolithic UI**: `app.py` is too large (34KB) and needs to be broken down into pages/components (Overview, Valuation, M&A, LBO, etc.).
- **Silent Fallbacks**: `data_loader.py` silently swaps real data for synthetic data. A Data Provenance layer must be introduced.
- **Error Handling**: Missing rigorous error handling and validation states (Model Health Check).
- **Hardcoded Logic in UI**: Some business logic might be entangled in `app.py`.
- **Inconsistent Reconciliations**: The Excel export writes static formulas that do not always match the Python logic (e.g., LBO Sponsor Equity).
