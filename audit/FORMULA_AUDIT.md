# Financial Formula Audit

## DCF Engine (`dcf_engine.py`)
- **WACC Calculation**: `wacc = (weight_equity * cost_of_equity) + (weight_debt * after_tax_cost_of_debt)`. Formula is correct.
- **UFCF Calculation**: `EBIT*(1-t) + D&A - CapEx - Delta NWC`. Formula is correct.
- **Terminal Value**: Uses Gordon Growth Model. 
  - **CRITICAL ERROR (Violation of Rule #5)**: The code intercepts `WACC - g <= 0` and silently changes the denominator to `0.005` and artificially reduces `g`. This must be removed. The model should instead throw a "Model Invalid" state if WACC <= Terminal Growth.
- **Enterprise to Equity Bridge**: `Equity Value = Enterprise Value - (Total Debt - Cash)`. Formula is correct.

## M&A Engine (`ma_engine.py`)
- **Purchase Price**: `Target Price * (1 + Premium) * Target Shares`. Correct.
- **Financing Mechanics**: Properly calculates cash/debt and stock portions based on mix.
- **New Shares Issued**: `Stock Portion / Acquirer Share Price`. Correct.
- **Debt Interest**: Calculated on `Cash Portion * Interest Rate * (1 - tax)`. Correct.
- **Pro-Forma EPS**: `(Acquirer NI + Target NI + After-Tax Synergies - After-Tax Interest) / Pro-Forma Shares`. Correct.

## LBO Engine (`lbo_engine.py`)
- **Entry Enterprise Value**: `Base EBITDA * Entry Multiple`. Correct.
- **Sponsor Initial Equity**: 
  - **CRITICAL ERROR (Violation of Rule #4)**: Calculated as `purchase_equity = entry_ev + target_net_debt`, then `sponsor_initial_equity = purchase_equity - total_debt_initial`. This effectively double-counts the target's net debt because Entry EV already represents the total value of the firm's operations. Target Net Debt is paid off using the debt/equity raised. Total Uses = Entry EV. Sponsor Equity should be `Entry EV - Total Debt Funded`.
- **Debt Waterfall (CADS)**: `FCF - Total Interest`. Senior paydown first, then subordinated. Correct.
- **Exit Valuation**: `Exit EBITDA * Exit Multiple`. Correct.
- **IRR/MoIC**: Standard cash flow formulation. Correct.
