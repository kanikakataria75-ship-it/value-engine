# ValuEngine

**Institutional financial modelling and transaction intelligence platform.**

ValuEngine V2 is a Python-based financial modeling platform that automates Discounted Cash Flow (DCF), M&A Accretion/Dilution, and Leveraged Buyout (LBO) analysis. It is designed to evaluate transactions with strict adherence to fundamental accounting identities, offering a defensible environment for testing scenarios, synergies, and deal structures.

## Architecture

The platform separates data ingestion, financial computation, and presentation into modular layers:
- **Data Loader & Data Quality Engine:** Ingests target and acquirer financials. Tags all data with provenance (e.g., `LIVE`, `DEMO`) and runs strict accounting checks (e.g., `Market Cap ≈ Price × Shares`, `EBITDA ≥ EBIT`). Data anomalies are classified as `HARD ERROR` or `WARNING`.
- **Valuation & Deal Engines (`dcf_engine.py`, `ma_engine.py`, `lbo_engine.py`, `comps_engine.py`):** Pure Python math libraries. They do not maintain state, ensuring reproducible scenario outputs.
- **Model Health & Analytics (`model_health.py`):** Cross-module validation that evaluates the overall transaction logic (e.g., checking if LBO entry equity is valid, or if M&A break-even synergies are mathematically plausible).
- **Financial brain (`mna_lbo_engine/modules/`):** The existing validated Python engines remain the sole source of truth for DCF, M&A, LBO, comps, risk, data quality, model health, and Excel generation. They are not duplicated in the API or frontend.
- **Service/API (`backend/`):** FastAPI provides validated, structured JSON responses. Every response has `status`, `data`, `warnings`, `errors`, and `provenance` fields.
- **Presentation (`frontend/`):** React + TypeScript + Vite institutional terminal. It holds UI state only; every financial output is requested from the API.
- **Fallback (`mna_lbo_engine/app.py`):** The previous Streamlit interface remains available as a reference/fallback and still calls the same engines.

## Core Methodologies

### DCF Valuation
- Projects 5-year Unlevered Free Cash Flow (UFCF) derived from Revenue, EBITDA Margin, D&A, CapEx, and ΔNWC.
- Terminal value is calculated using the Gordon Growth Method.
- Supports both **Year-End** and **Mid-Year** discounting conventions (toggling this affects both Python math and Excel exports).
- Explicit guardrails: Raises strict `ValueError` if `WACC <= Terminal Growth` to prevent asymptotic valuation inflation.
- Evaluates economic spread via `ROIC - WACC`.

### M&A Accretion / Dilution
- Models transaction structuring across Cash vs. Stock consideration and Offer Premium.
- Separates explicit **Revenue Synergies** and **Cost Synergies** (both taxed at the corporate rate).
- Accounts for one-time **Integration Costs**.
- Calculates Pro-Forma Net Income, New Shares Issued, and EPS Accretion / Dilution.
- Includes a numerical **Break-Even Analysis** identifying the minimum pre-tax synergy required to achieve EPS accretion.

### Leveraged Buyout (LBO)
- Structures entry EV into Senior Debt, Subordinated Debt, and Sponsor Equity (Sources & Uses).
- 5-Year operating model flows into a strict Cash Available for Debt Service (CADS) waterfall.
- Debt schedule tracks beginning balances, interest, mandatory paydowns, cash sweeps, and ending balances.
- Calculates Internal Rate of Return (IRR) and Multiple on Invested Capital (MoIC) with fallback logic for non-converging cash flows.
- **Returns Attribution:** Bridges initial equity to exit equity via EBITDA Growth, Multiple Expansion, Debt Paydown, and Cash Generation.

### Trading & Transaction Comps
- Extracts EV/Rev, EV/EBITDA, and P/E (or TV multiples for transactions).
- Computes statistical distributions (Min, 25th, Median, Mean, 75th, Max).
- Implies target equity value based on peer medians for valuation triangulation.

## Testing & Validation
The project includes a robust testing suite `test_reconciliation.py` using `pytest`.
Tests ensure:
- Python LBO output matches the strict algebraic output of the generated Excel formulas.
- Mid-Year vs Year-End DCF discount factors strictly match the expected `^t` vs `^(t-0.5)` logic.
- Graceful failure under edge cases (e.g., negative EBITDA, missing shares).

## Deployment Instructions

### Prerequisites
- Python 3.10+
- `pip install -r requirements.txt`

### Running the New Application

Install backend packages from the repository root:

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the address printed by Vite (normally `http://localhost:5173`). The API documentation is available at `http://127.0.0.1:8000/docs`.

### Demonstration Data

No live market-data provider is configured. The only available companies are the existing `AAPL`, `MSFT`, and `NVDA` presets, shown throughout the product as **DEMONSTRATION DATA**. Unknown tickers and unavailable transaction comps return explicit `UNAVAILABLE` states; the UI does not invent missing financial values, historical prices, or transactions.

### Legacy Streamlit Fallback
```bash
streamlit run mna_lbo_engine/app.py
```

### Running Tests
```bash
python -m pytest tests/ -v
```

The suite includes the original financial-engine reconciliation tests and FastAPI contracts for DCF, M&A, LBO, comps, model health, data quality, explicit invalid/unavailable states, and Excel export.

## API Domains

- `/api/company` — preset company context and provenance
- `/api/dcf` — DCF calculation and engine-driven sensitivity matrices
- `/api/mna`, `/api/lbo`, `/api/comps` — transaction and valuation engines
- `/api/analytics` — Monte Carlo and LBO stress outputs
- `/api/model-health`, `/api/data-quality` — validation diagnostics
- `/api/reports/excel` — existing audit-ready Excel workbook export

## Known Limitations
- **LBO Working Capital:** Working capital changes are modelled as a static percentage of incremental revenue; dynamic historical NWC days are not currently extrapolated.
- **M&A Taxes:** Synergies are assumed to be taxed immediately at the blended corporate rate. Net Operating Loss (NOL) carryforwards and Section 382 limitations are not modelled.
- **Data Availability:** Live API fetching is subject to provider rate limits. If data is unavailable, the system defaults to verified internal DEMO data to prevent crashing, explicitly flagged by the Provenance Engine.
