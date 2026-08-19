# ValuEngine 

[![Status](https://img.shields.io/badge/Status-Active%20Production-brightgreen)](#)
[![Frontend](https://img.shields.io/badge/Frontend-React%2018%20%7C%20TypeScript%20%7C%20Vite-646CFF)](#)
[![Backend](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.11-009688)](#)
[![Analytics](https://img.shields.io/badge/Quantitative%20Analytics-R%20%7C%20Rscript-276DC3)](#)
[![AI Engine](https://img.shields.io/badge/AI%20Copilot-Google%20Gemini%20%7C%20Streaming-8E75B2)](#)
[![Database](https://img.shields.io/badge/Local%20Store-SQLite%20%7C%20WAL%20Mode-003B57)](#)
[![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen)](#)

> **Institutional-grade financial valuation, M&A transaction modeling, and quantitative risk engineering platform.**

ValuEngine is a comprehensive financial intelligence workspace designed for investment bankers, corporate finance teams, and quantitative analysts. It unifies deterministic deal modeling (DCF, M&A Accretion/Dilution, LBO, Multiples) with probabilistic risk engineering (R-powered Monte Carlo, Copulas, Merton default probability, Tail Risk) and a context-aware AI Financial Copilot.

---

## Table of Contents

- [Key Platform Features](#-key-platform-features)
  - [1. Context-Aware AI Financial Copilot](#1-context-aware-ai-financial-copilot)
  - [2. R Analytics & Valuation Risk Lab](#2-r-analytics--valuation-risk-lab)
  - [3. Core Valuation & Deal Modeling Engines](#3-core-valuation--deal-modeling-engines)
  - [4. High-Performance Local Financial Store](#4-high-performance-local-financial-store)
  - [5. Institutional Terminal UI & Experience](#5-institutional-terminal-ui--experience)
  - [6. Audit Trail, Health Diagnostics & Excel Export](#6-audit-trail-health-diagnostics--excel-export)
- [System Architecture](#-system-architecture)
- [Quantitative Methodology & Formulations](#-quantitative-methodology--formulations)
- [Screenshots & Visual Showcase](#-screenshots--visual-showcase)
- [Getting Started & Installation](#-getting-started--installation)
  - [Prerequisites](#prerequisites)
  - [1. Backend Setup](#1-backend-setup)
  - [2. R Analytics Environment Setup](#2-r-analytics-environment-setup)
  - [3. Frontend Terminal Setup](#3-frontend-terminal-setup)
  - [4. Seeding & Ingesting Market Data](#4-seeding--ingesting-market-data)
- [Running Automated Tests](#-running-automated-tests)
- [API Endpoints Reference](#-api-endpoints-reference)
- [Project Structure](#-project-structure)
- [License & Contributing](#-license--contributing)

---

## Key Platform Features

### 1. Context-Aware AI Financial Copilot
- **Workspace Context Awareness:** The copilot continuously monitors the user's active company ticker, financial parameters, valuation metrics, and active module (DCF, M&A, LBO, Risk Lab).
- **Intelligent Financial Advisory:** Explains complex valuation formulas, provides actionable deal structuring suggestions (e.g. debt capacity optimization, synergy break-even requirements), and interprets statistical risk metrics in plain English.
- **Provider Architecture:** Powered by Google Gemini with streaming responses and an intelligent fallback engine to guarantee zero-downtime execution even without external API credentials.
- **Interactive Sliding Panel:** Always accessible across all pages with quick-prompt shortcuts for instant sensitivity audits and valuation sanity checks.

### 2. R Analytics & Valuation Risk Lab
ValuEngine embeds a suite of 8 quantitative engines written in native **R** with a seamless Python bridge and robust algorithmic fallback solvers:
1. **Monte Carlo Simulation (`monte_carlo.R`):** Correlated multi-parameter stochastic cash flow generation across revenue growth, margin expansion, and cost of capital (1,000–100,000 iterations). Generates empirical value distributions, VaR/CVaR, and probability density functions.
2. **Student-t & Gaussian Copulas (`copula.R`):** Models non-linear dependencies and extreme joint fat-tail risk across valuation assumptions.
3. **Merton Structural Credit Model (`merton.R`):** Black-Scholes-Merton option-theoretic default risk solver estimating unobserved asset value ($V_A$), structural volatility ($\sigma_A$), Distance-to-Default ($DD$), and 1-year Default Probability ($PD$).
4. **Value at Risk & Expected Shortfall (`var_cvar.R`):** Parametric, historical, and Cornish-Fisher non-Gaussian skewness/kurtosis-adjusted tail risk estimations at 95% and 99% confidence intervals.
5. **Extreme Value Theory / Tail Risk (`tail_risk.R`):** Generalized Pareto Distribution (GPD) and Peaks-Over-Threshold (POT) modeling to stress-test 1-in-100-year market dislocation shocks.
6. **Regime-Switching Volatility (`regime.R`):** Markov-switching state models classifying market regimes between low-volatility expansionary states and high-volatility crisis periods.
7. **Macro Factor Sensitivities (`factor_model.R`):** Multi-factor linear regressions assessing asset sensitivity against 10-year Treasury yields, CPI inflation, GDP growth rates, and credit spreads.
8. **Assumption Impact / Tornado Engine (`assumption_impact.R`):** Elasticity matrices and tornado impact rankings identifying which single operational parameter exerts the highest sensitivity on Enterprise and Equity values.

### 3. Core Valuation & Deal Modeling Engines
- **Discounted Cash Flow (DCF):**
  - Projects 5-year discrete Unlevered Free Cash Flows (UFCF) derived from Revenues, EBITDA Margins, D&A, CapEx, and $\Delta\text{NWC}$.
  - Supports dual discounting conventions: **Mid-Year** vs. **Year-End** discounting.
  - Dual Terminal Value methodology: **Gordon Growth Model** vs. **Exit EBITDA Multiple**.
  - Strict mathematical guardrails ($WACC > g$) preventing asymptotic model explosions, with real-time economic spread evaluation ($\text{ROIC} - \text{WACC}$).
- **M&A Accretion / Dilution Engine:**
  - Multi-tranche financing mix modeling: Cash consideration, Stock issuance, and Acquirer Debt issuance.
  - Comprehensive synergy modeling: Explicit pre-tax Cost Synergies, Revenue Synergies, and one-off Integration costs.
  - Generates Pro-Forma Net Income, Shares Outstanding, EPS Accretion/Dilution ($ and %), and an analytical **Break-Even Synergy** solver.
- **Leveraged Buyout (LBO) Engine:**
  - Sources & Uses structuring spanning Senior Debt, Subordinated Debt, Mezzanine, and Sponsor Equity.
  - Dynamic 5-year Cash Available for Debt Service (CADS) debt sweep waterfall with mandatory amortization and interest schedules.
  - Calculates exit Enterprise Value, Sponsor IRR, MoIC, and a 4-pillar **Returns Attribution Bridge** (EBITDA Growth, Multiple Expansion, Debt Paydown, Cash Generation).
- **Trading & Transaction Comparable Multiples:**
  - Standardized multiples extraction (EV/Revenue, EV/EBITDA, P/E, EV/EBIT).
  - Harmonic and arithmetic distributions (Min, 25th percentile, Median, Mean, 75th percentile, Max) with target equity value triangulation.

### 4. High-Performance Local Financial Store
- **Instant Offline Data Access:** Built-in high-speed SQLite database engine (`data/financial_data.db`) operating in Write-Ahead Logging (WAL) mode for zero-latency lookups.
- **Pre-Ingested 100+ Company Universe:** Contains detailed balance sheets, income statements, cash flow statements, historical trading multiples, and risk profiles across S&P 500 and global equities.
- **Multi-Source Ingestion Pipeline:** Automated ingestion tools supporting Yahoo Finance (`yfinance`) and Alpha Vantage with intelligent fallback, schema normalization, and automated metric derivation.

### 5. Institutional Terminal UI & Experience
- **Interactive Dark / Light Modes:** Bespoke dark financial terminal theme with custom glassmorphism, glowing telemetry cards, and rich color accents.
- **Rich Recharts Visualizations:** Interactive tornado sensitivity charts, fan chart probability densities, debt paydown waterfalls, M&A synergy bars, and trading multiple ranges.
- **Command Palette & Global Search:** Instant company lookup and active status telemetry across all pages.

### 6. Audit Trail, Health Diagnostics & Excel Export
- **Dynamic Excel Export (`/api/reports/excel`):** Generates live `.xlsx` workbooks populated with native Excel formulas (`=SUM`, `=NPV`, `=IRR`, dynamic debt logic), ready for presentation to investment committees.
- **Data Provenance & Audit Page:** Tracks every data field to its origin (`LIVE_API`, `LOCAL_STORE`, `DEMO_FALLBACK`), highlighting reconciliation checks and balance sheet equilibrium ($A = L + E$).
- **Model Health Scanner:** Real-time cross-validation alerting users to insolvency hazards, negative entry equity, or unrealistic synergy assumptions.

---

## System Architecture

```mermaid
flowchart TB
    subgraph Frontend ["Frontend Terminal (React 18 + TypeScript + Vite)"]
        UI[App Shell & Navigation]
        Pages[DCF | M&A | LBO | Comps | Risk Lab | Audit | Reports]
        CopilotUI[Sliding AI Copilot Drawer]
        Theme[Dark / Light Theme Provider]
    end

    subgraph Backend ["Backend API Layer (FastAPI)"]
        API[REST Endpoints /api/...]
        CopilotService[AI Provider & Context Builder]
        ValuationService[Valuation Dispatcher]
    end

    subgraph Engines ["Financial Brain & Math Engines"]
        DCF[dcf_engine.py]
        MNA[ma_engine.py]
        LBO[lbo_engine.py]
        COMPS[comps_engine.py]
        HEALTH[model_health.py]
        EXCEL[excel_generator.py]
    end

    subgraph RAnalytics ["R Quantitative Risk Lab"]
        RBridge[r_risk_engine.py / r_integration.py]
        RScripts["R Scripts (Monte Carlo, Merton, Copula, VaR/CVaR, EVT, Regime, Factor)"]
        PyFallback[Vectorized NumPy/SciPy Fallback Solver]
    end

    subgraph Storage ["Data Layer & Local Financial Store"]
        SQLite[Local SQLite Cache (WAL Mode)]
        Ingestor[Bulk Ingestion Pipeline]
        Providers[Yahoo Finance / Alpha Vantage]
    end

    UI --> API
    CopilotUI --> CopilotService
    API --> ValuationService
    ValuationService --> Engines
    ValuationService --> RBridge
    RBridge --> RScripts
    RScripts -.->|Fallback if R missing| PyFallback
    ValuationService --> SQLite
    Ingestor --> Providers --> SQLite
    Engines --> EXCEL --> UI
```

---

## Quantitative Methodology & Formulations

### 1. DCF Mid-Year Convention Formula
$$\text{PV}(\text{UFCF}_t) = \frac{\text{UFCF}_t}{(1 + \text{WACC})^{t - 0.5}}$$

$$\text{Terminal Value}_{\text{Gordon}} = \frac{\text{UFCF}_5 \times (1 + g)}{\text{WACC} - g}$$

### 2. Merton Structural Default Model
Under the Merton framework, firm equity is treated as a European call option on total assets $V_A$ with strike price equal to debt face value $D$:

$$E = V_A \mathcal{N}(d_1) - D e^{-rT} \mathcal{N}(d_2)$$

$$\sigma_E E = \mathcal{N}(d_1) \sigma_A V_A$$

Where Distance-to-Default ($DD$) and Default Probability ($PD$) are derived as:

$$DD = \frac{\ln(V_A / D) + (\mu - 0.5 \sigma_A^2)T}{\sigma_A \sqrt{T}}, \quad PD = \mathcal{N}(-DD)$$

### 3. M&A EPS Accretion / Dilution Break-Even
$$\text{Pre-Tax Break-Even Synergy} = \frac{\text{Target Net Income} - \text{Foregone Interest} - \text{New Debt Interest}}{\text{Acquirer Target Multiple}} \times \frac{1}{1 - t_c}$$

---

## Screenshots & Visual Showcase

| Risk Lab | Valuation & M&A Overview | LBO | DCF |
| :---: | :---: | :---: | :---: |
| <img width="3384" height="1320" alt="Screenshot 2026-08-19 114648" src="https://github.com/user-attachments/assets/294f6154-52e5-4193-b62c-5a86d588b8c9" /> | <img width="3393" height="1278" alt="Screenshot 2026-08-19 114655" src="https://github.com/user-attachments/assets/37f33c05-014d-4ed3-bea5-cbfef7e6528f" /> | <img width="3387" height="1284" alt="Screenshot 2026-08-19 114703" src="https://github.com/user-attachments/assets/8e49a15e-7e17-467a-990f-1d91d5ad8769" /> | <img width="3364" height="1290" alt="Screenshot 2026-08-19 114710" src="https://github.com/user-attachments/assets/8568a5af-407f-485d-a3ab-441dcc1c41ea" /> | 



---

## Getting Started & Installation

### Prerequisites
- **Python:** Version `3.10` or higher
- **Node.js:** Version `18.x` or higher (`npm` included)
- **R (Optional, for full R Risk Lab execution):** Version `4.0+` with packages: `copula`, `fGarch`, `depmixS4`, `evir`, `jsonlite`

---

### 1. Backend Setup

Clone the repository and install the Python dependencies:

```bash
# Clone repository
git clone https://github.com/kanikakataria75-ship-it/value-engine.git
cd value-engine

# Create & activate a virtual environment (recommended)
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Start the FastAPI application server:

```bash
uvicorn backend.main:app --reload --port 8000
```
*Backend runs on `http://127.0.0.1:8000`. Interactive OpenAPI documentation available at `http://127.0.0.1:8000/docs`.*

---

### 2. R Analytics Environment Setup (Optional)

To enable the native R analytics engine for the Valuation Risk Lab:

```bash
# Automatically detects R and installs required CRAN packages
python setup_r.py
```
*(Note: If R is not installed on the system, ValuEngine automatically engages its high-performance **vectorized Python math fallback**, ensuring all Risk Lab simulations remain 100% functional).*

---

### 3. Frontend Terminal Setup

In a new terminal window, initialize the React client:

```bash
cd frontend
npm install
npm run dev
```
*Frontend terminal launches at `http://localhost:5173`.*

---

### 4. Seeding & Ingesting Market Data

To populate the local SQLite financial store with 100+ tickers:

```bash
# Ingest the company universe
python scripts/seed_company_universe.py
```

---

## Running Automated Tests

ValuEngine includes an exhaustive testing suite covering arithmetic reconciliation, financial identities, API endpoints, AI copilot responses, and risk simulations:

```bash
# Run all unit and integration tests
pytest tests/ -v

# Run brain validation financial verification suite
python brain_validation/run_all.py
```

---

## API Endpoints Reference

| Route | Method | Description |
| :--- | :--- | :--- |
| `/api/company/{ticker}` | `GET` | Fetches historical financials, balance sheet, and market data |
| `/api/company/universe/all` | `GET` | Lists all 100+ tickers in the local store universe |
| `/api/dcf` | `POST` | Executes DCF valuation with mid-year convention and sensitivity |
| `/api/mna` | `POST` | Calculates M&A accretion/dilution, synergies, and break-even |
| `/api/lbo` | `POST` | Solves 5-year LBO debt schedule, returns, and attribution |
| `/api/comps` | `POST` | Computes statistical peer trading & transaction multiples |
| `/api/risk-lab/all` | `POST` | Runs full suite of 8 quantitative risk models (Monte Carlo, Merton, etc.) |
| `/api/copilot/chat` | `POST` | Streaming AI copilot financial advisory endpoint |
| `/api/data-quality` | `GET` | Executes balance sheet and accounting identity audits |
| `/api/model-health` | `POST` | Real-time cross-engine transaction sanity check |
| `/api/reports/excel` | `POST` | Exports an audit-ready dynamic `.xlsx` valuation workbook |

---

## Project Structure

```
valuengine/
├── backend/
│   ├── main.py                     # FastAPI application & router endpoints
│   ├── schemas/models.py           # Pydantic data schemas & request validation
│   └── services/
│       ├── ai_provider.py          # AI Copilot streaming engine & context manager
│       └── valuation_service.py    # Service dispatching calculations to engines
├── frontend/
│   ├── src/
│   │   ├── components/             # AppShell, CopilotPanel, UI design system
│   │   ├── context/ThemeContext.tsx# Dark / Light theme provider
│   │   ├── pages/                  # DCF, M&A, LBO, RiskLab, Comps, Audit, Reports
│   │   ├── services/api.ts         # Type-safe Axios client
│   │   └── types/api.ts            # TypeScript interfaces
│   ├── package.json
│   └── vite.config.ts
├── mna_lbo_engine/
│   └── modules/
│       ├── bulk_data_ingestor.py   # High-throughput market data pipeline
│       ├── comps_engine.py         # Multiples and peer statistics
│       ├── data_loader.py          # Provenance-tagged data ingestion
│       ├── dcf_engine.py           # 5-Year UFCF & Terminal Value models
│       ├── excel_generator.py      # Native formula Excel builder
│       ├── lbo_engine.py           # Sources/Uses & CADS debt schedules
│       ├── local_financial_store.py# SQLite persistence layer (WAL mode)
│       ├── ma_engine.py            # Accretion/dilution & synergies
│       ├── model_health.py         # Financial sanity & identity verification
│       ├── r_integration.py        # Rscript subprocess connector
│       └── r_risk_engine.py        # Risk dispatcher & Python fallback solver
├── r_analytics/valuation_risk/
│   ├── assumption_impact.R         # Tornado & sensitivity rankings
│   ├── copula.R                    # Student-t & Gaussian copula dependencies
│   ├── factor_model.R              # Macro factor regression sensitivities
│   ├── merton.R                    # Structural credit default model
│   ├── monte_carlo.R               # High-iteration correlated simulation
│   ├── regime.R                    # Markov regime-switching volatility
│   ├── risk_metrics.R              # Distribution summary statistics
│   ├── tail_risk.R                 # Extreme Value Theory (EVT/GPD)
│   └── var_cvar.R                  # Cornish-Fisher VaR & Expected Shortfall
├── data/                           # Universe CSVs & ingestion manifests
├── scripts/                        # Database seeding & ingestion utilities
├── tests/                          # Comprehensive pytest test suite
├── setup_r.py                      # Automatic R environment configuration
└── requirements.txt                # Python dependencies
```

---

## License & Contributing

Distributed under the MIT License. Contributions, feedback, and issue submissions are welcome. Please ensure all tests pass (`pytest tests/ -v`) prior to submitting pull requests.
