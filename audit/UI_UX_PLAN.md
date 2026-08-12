# UI/UX Redesign Plan

## Current State
- The Streamlit application (`app.py`) is a monolithic script presenting a generic dashboard style.
- It likely exposes all calculations and inputs on the main screen, lacking progressive disclosure.
- UI elements do not distinguish between inputs, outputs, defaults, and API-fetched data clearly.

## Target Aesthetic: Premium Investment Banking Terminal
- **Color Palette**: 
  - Deep Charcoal / Near-Black for dark mode.
  - Warm White / Off-White for light mode.
  - Meaningful accents: Green (positive), Red (negative), Amber (warnings).
- **Typography & Layout**:
  - High information density (Bloomberg-inspired).
  - Clean, restrained, and elegant.
  - Avoid excessive borders, rounded containers, and emojis.
- **Progressive Disclosure**:
  - The landing page (Overview) should answer the most critical questions immediately (What company? Valuation? EPS Accretion? IRR?).
  - Detailed calculations (Debt Schedule, Operating Model) should be organized into separate tabs/sections.

## New Navigation Structure
The monolith will be broken down into a multi-page/multi-tab structure:
1. **Overview**: Executive summary, deal quality score, primary metrics.
2. **Valuation**: DCF, Trading Comps, Valuation Summary (Range/Football Field).
3. **Transactions**: M&A mechanics, Accretion/Dilution, Deal Scenarios.
4. **LBO**: Sources & Uses, Debt Schedule, Returns, Sensitivities.
5. **Analytics**: Assumption Risk Map, Deal Quality Dashboard, Model Diagnostics.
6. **Data & Settings**: Data provenance, Data freshness, Data Quality warnings.

## Smart Features Integration
- **Assumption Risk Map**: Visually rank the most sensitive assumptions (e.g., WACC, Entry Multiple).
- **Model Health Check**: Persistent UI indicator (🟢 VALID, 🟡 REVIEW REQUIRED, 🔴 INVALID).
- **Deal Quality Score**: Transparent score composed of distinct valuation/risk metrics.
- **Financial Copilot**: A side-panel or inline assistant explaining the model state using *only* model data (no hallucinations).
