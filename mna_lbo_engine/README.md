# M&A Accretion/Dilution & LBO Valuation Engine
**Institutional Quantitative Corporate Finance & Automated Financial Modeling Suite**

---

## Executive Overview
The **M&A Accretion/Dilution & LBO Valuation Engine** is an institutional-grade Python application designed for quantitative investment banking, private equity valuation, and corporate financial engineering. The suite automatically ingests real-time financial statement data via `yfinance`, performs standalone 5-year DCF intrinsic valuations, models complex M&A transaction mechanics (Cash vs. Stock financing mix, purchase price allocation, pre/after-tax cost synergies), and simulates a 5-year Leveraged Buyout (LBO) deal with multi-tranche debt waterfalls (Senior & Subordinated) and CADS cash sweep debt paydowns.

The platform provides both an interactive **Streamlit** dashboard with **Plotly** sensitivity heatmaps and an **openpyxl** Excel report generator that writes **LIVE EXCEL FORMULAS** (`=SUM()`, `=IRR()`, `=IF()`, `=(1-t)`) into styled, audit-ready financial workbooks.

---

## Code Architecture & File Structure

```
mna_lbo_engine/
├── app.py                      # Interactive Streamlit dashboard & Plotly UI
├── config.py                   # Default parameters, constants, and tax/rate assumptions
├── requirements.txt            # Python dependencies (yfinance, pandas, numpy, numpy-financial, openpyxl, streamlit, plotly)
├── README.md                   # Wall Street institutional documentation & resume bullet points
└── modules/
    ├── __init__.py
    ├── data_loader.py          # Real-time financial statement fetching & standardization via yfinance
    ├── dcf_engine.py           # 5-Year UFCF forecast, CAPM WACC, Gordon Growth TV, Intrinsic Valuation
    ├── ma_engine.py            # Cash vs Stock deal mechanics, Synergies, Debt interest, EPS Accretion/Dilution
    ├── lbo_engine.py           # Senior/Sub Debt tranches, 5-Year CADS cash sweep, Exit Multiple, IRR & MoIC
    └── excel_exporter.py       # openpyxl engine exporting formatted workbooks with live Excel formulas
```

---

## Core Financial Engine & Mathematical Foundations

### 1. Standalone Discounted Cash Flow (DCF) & CAPM WACC
* **CAPM Cost of Equity ($R_e$):**
  $$R_e = R_f + \beta \times \text{ERP}$$
  *Where $R_f = 4.2\%$ (10Y US Treasury), $\text{ERP} = 5.5\%$ (Equity Risk Premium).*
* **Weighted Average Cost of Capital (WACC):**
  $$\text{WACC} = \left(\frac{E}{D + E}\right) R_e + \left(\frac{D}{D + E}\right) R_d \times (1 - t)$$
* **Unlevered Free Cash Flow (UFCF):**
  $$\text{UFCF}_t = \text{EBIT}_t \times (1 - t) + \text{D\&A}_t - \text{CapEx}_t - \Delta \text{NWC}_t$$
* **Gordon Growth Terminal Value (TV):**
  $$\text{TV}_5 = \frac{\text{UFCF}_5 \times (1 + g)}{\text{WACC} - g}$$
* **Enterprise & Equity Value:**
  $$\text{Enterprise Value} = \sum_{t=1}^{5} \frac{\text{UFCF}_t}{(1 + \text{WACC})^t} + \frac{\text{TV}_5}{(1 + \text{WACC})^5}$$
  $$\text{Equity Value} = \text{Enterprise Value} - \text{Total Debt} + \text{Cash \& Equivalents}$$

### 2. M&A Accretion / Dilution Engine
* **Offer Price & Purchase Price:**
  $$\text{Offer Price} = \text{Target Spot Price} \times (1 + \text{Premium \%})$$
  $$\text{Total Purchase Price} = \text{Offer Price} \times \text{Target Shares Outstanding}$$
* **Financing Mechanics & New Shares Issued:**
  $$\text{New Shares Issued} = \frac{\text{Purchase Price} \times \text{\% Stock}}{\text{Acquirer Spot Price}}$$
  $$\text{After-Tax Debt Interest} = (\text{Purchase Price} \times \text{\% Cash}) \times R_{\text{debt}} \times (1 - t)$$
* **Pro-Forma Combined Net Income:**
  $$\text{Net Income}_{\text{Pro-Forma}} = \text{NI}_{\text{Acquirer}} + \text{NI}_{\text{Target}} + \text{Synergies} \times (1 - t) - \text{Interest}_{\text{After-Tax}}$$
* **EPS Accretion / Dilution %:**
  $$\text{Accretion / Dilution \%} = \left( \frac{\text{EPS}_{\text{Pro-Forma}}}{\text{EPS}_{\text{Acquirer Standalone}}} - 1 \right) \times 100$$

### 3. LBO Simulator & CADS Debt Waterfall Sweep
* **Entry Enterprise Value & Sponsor Equity:**
  $$\text{Entry EV} = \text{EBITDA}_0 \times \text{Entry Multiple}$$
  $$\text{Sponsor Initial Equity} = \text{Entry EV} + \text{Net Debt}_{\text{Target}} - \text{Total Debt Funded}$$
* **Cash Available for Debt Service (CADS):**
  $$\text{CADS}_t = \text{FCF}_t - (\text{Senior Interest}_t + \text{Subordinated Interest}_t)$$
  *CADS pays down Senior Debt principal first, then Subordinated Debt.*
* **Sponsor 5-Year Exit IRR & MoIC:**
  $$\text{Exit Equity Value} = (\text{EBITDA}_5 \times \text{Exit Multiple}) - \text{Ending Total Debt} + \text{Ending Cash}$$
  $$\text{MoIC (Cash-on-Cash Return)} = \frac{\text{Exit Equity Value}}{\text{Sponsor Initial Equity}}$$
  $$\text{IRR Solution:} \quad 0 = -\text{Equity}_{\text{Initial}} + \frac{\text{Equity}_{\text{Exit}}}{(1 + \text{IRR})^5}$$

---

## Live Excel Formula Exporting

The `excel_exporter.py` module utilizes `openpyxl` to build an institutional 4-tab workbook (`M_and_A_LBO_Model.xlsx`) formatted with Corporate Navy headers (`#1B365D`), accounting double-underlines, and standard financial number formatting.

**Key Distinction:** Cells contain active uppercase Excel formulas rather than static values:
- `=SUM(B20:F20)`
- `=(F18*(1+$C$5))/($C$4-$C$5)`
- `=C26/C28`
- `=IRR(B37:G37)`
- `=(C19/C12)^(1/5)-1`

---

## Installation & Operating Guide

### Prerequisites
- Python 3.9+ installed.

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Launch Interactive Streamlit Dashboard
```bash
streamlit run app.py
```

---

## Institutional Resume / Portfolio Bullet Points

* **Automated M&A Accretion/Dilution & LBO Valuation Engine (Python, Streamlit, OpenPyXL, Plotly):** Built a production-grade quantitative corporate finance portal integrating real-time market data (`yfinance`), 5-year DCF intrinsic valuations, M&A cash vs. stock financing mechanics, and 5-year LBO multi-tranche debt paydown waterfalls (Senior/Subordinated debt CADS sweeps).
* **Live Excel Formula Generation & Sensitivity Analysis:** Engineered an openpyxl financial reporting engine that outputs audit-ready multi-tab Excel models writing live Excel formulas (`=SUM()`, `=IRR()`, `=(1-t)`), paired with dynamic Plotly sensitivity matrices evaluating WACC vs. Terminal Growth and Entry Multiples vs. Leverage Ratios for Wall Street institutional presentation.
