# ValuEngine methodology

## Principles

ValuEngine is built on five rules.

1. **Every company is modelled on its own numbers.** Baselines come from the company's own statements, its own history and its own country's market parameters. No template margins are borrowed from other companies, and no US rates are applied to Indian companies.
2. **Every number carries its provenance.** Each stored figure records its source, fiscal period, reporting currency and retrieval date. Anything the pipeline had to derive is flagged as derived.
3. **One scenario feeds every output.** The analyst's assumptions are stored as overrides on top of the company baseline. The DCF, sensitivity grids, Monte Carlo, Expectations Lab, Excel workbook, IC memo and ValuAI copilot all receive the same scenario, so they cannot disagree.
4. **Models refuse rather than guess.** When an input is missing or a calculation is undefined (for example WACC at or below terminal growth, or negative book equity in an excess-return model), the API returns `INVALID` or `UNAVAILABLE` with a reason instead of a number.
5. **Diagnostics come with the numbers.** Each result carries flags (`INVALID`, `REVIEW` or `INFO`) describing assumptions that deserve a second look.

## Data pipeline

**Sources.** Annual income statements, balance sheets, cash-flow statements and daily prices come from Yahoo Finance (via `yfinance`). FX rates are Yahoo Finance daily USD/INR closes. Live mode can optionally query Alpha Vantage and falls back to the local store, labelled `LOCAL_FALLBACK`, when the provider is unavailable or rate-limited.

**Store.** Everything is persisted in a local SQLite database (`data/financial_data.db`) with four tables:

- company fundamentals
- daily prices
- four fiscal years of statement history
- dated FX rates

A compressed CSV snapshot in `data/snapshot/` rebuilds the database on first run without any network access.

**Currency.** Some companies report statements in one currency but trade in another. Those statements are restated into the trading currency, so that market capitalisation, enterprise value and per-share values are always consistent.

**Statement anchoring.** The latest complete fiscal-year column is used for every field, so revenue from one year is never mixed with debt from another.

**Reconciliation.** Reported EBITDA below EBIT is impossible, so EBITDA is rebuilt as EBIT + D&A and flagged as derived. Missing capital expenditure is estimated from the company's own historical capex-to-revenue ratio and flagged. Nothing is filled with generic defaults.

**Quality checks.** Every record passes a rule-based check before any model runs:

| Severity | Examples |
|---|---|
| ERROR | missing or non-positive revenue, price or share count; negative debt or cash balances |
| WARNING | EBIT above EBITDA; EBITDA above revenue; market cap differs from price × shares by more than 10%; suspected currency mismatch; assets differ from liabilities + equity by more than 5%; negative book equity; stale fundamentals (> 460 days) |
| INFO | loss-making; derived fields; balance-sheet financial classification; beta source |

The quality score is `100 − 40 × errors − 8 × warnings`, floored at zero. Completeness is measured over 17 core fields. Records with errors are rejected at ingestion.

## Baseline assumptions

Market parameters are set per currency:

| | United States (USD) | India (INR) |
|---|---|---|
| Risk-free rate | 4.20% | 6.50% |
| Equity risk premium | 5.50% | 7.00% |
| Credit spread | 1.50% | 2.00% |
| Tax rate | 21.00% | 25.17% |
| Terminal growth | 2.50% | 5.00% |
| Long-run nominal growth anchor | 5.00% | 10.00% |

**Revenue growth** = 60% × the company's own revenue CAGR + 40% × the country's growth anchor, bounded to [−5%, 25%]. Growth rates mean-revert, so neither pure history nor a pure anchor is used.

**Target EBITDA margin** is the latest fiscal-year actual. The DCF ramps linearly from the actual margin to the target, so a changed target is reached in year N rather than overnight.

**CapEx and D&A** are the company's multi-year averages as a share of revenue, or the latest year when no history exists. **Net working capital** absorbs 5% of incremental revenue.

**Beta.**

- US companies use the provider beta (a 5-year monthly regression against the S&P 500) when it lies within [0.3, 3.0].
- Indian companies use a one-year daily regression against a cap-weighted index of Indian stocks in the universe, Blume-adjusted (`0.67 × raw + 0.33`). A beta measured against the S&P 500 says nothing about an Indian stock's systematic risk.

**Cost of capital.**

- Cost of equity = `rf + β × ERP`.
- Pre-tax cost of debt = `rf + spread + leverage premium`, where the premium is +1% above 3× net debt / EBITDA and +2.5% above 5×.
- WACC weights use market equity and book debt, and WACC is bounded between `rf + 1%` and 25%.

**Terminal growth** is the country rate, capped at `WACC − 2%`. **RONIC** (return on new invested capital) is the company's after-tax ROIC, bounded between WACC and 40%.

## Discounted cash flow

The DCF values unlevered free cash flow to the firm over N years (default 5):

```
Revenue_t = Revenue_0 × (1 + g)^t
Margin_t  = Margin_0 + (Target − Margin_0) × t / N
EBIT_t    = Revenue_t × Margin_t − D&A_t
UFCF_t    = EBIT_t − tax(EBIT_t) + D&A_t − CapEx_t − NWC% × (Revenue_t − Revenue_{t−1})
```

Tax applies only to positive EBIT. With the mid-year convention, cash flows are discounted at `t − 0.5`.

**Terminal value, perpetuity method.** The value-driver formula replaces the classic Gordon growth model:

```
TV = NOPAT_{N+1} × (1 − g / RONIC) / (WACC − g)
```

Growth must be paid for. At a return of RONIC on new capital, growing at g requires reinvesting g / RONIC of NOPAT. The classic `UFCF_N × (1 + g) / (WACC − g)` silently assumes the reinvestment rate of the final forecast year continues forever, which overstates value whenever that year's investment is too low for the growth assumed.

**Terminal value, exit-multiple method.** `EBITDA_N × multiple`, discounted from the end of year N.

**Equity bridge.** Equity = EV − total debt + cash. Value per share = equity / diluted shares outstanding.

**Diagnostics.**

- **REVIEW flags:**
  - terminal value above 85% of enterprise value
  - a spread between WACC and terminal growth below 1.5%
  - terminal growth above the risk-free rate
  - negative equity value
  - revenue growth above 25% a year
- **INFO flags:**
  - free cash flow negative in any projection year
  - a target margin more than 10 points from the actual
- **INVALID:** WACC at or below terminal growth.

**Sensitivity.** Two 5 × 5 grids: WACC × terminal growth, and revenue growth × target margin. The cells are coloured against the market price.

## Banks and insurers

Balance-sheet financials use an **excess-return (residual income)** model:

- Free cash flow is meaningless when debt is raw material rather than financing.
- A DCF of a bank double-counts its funding.

A company is classified as balance-sheet financial if it meets any of these conditions:

- it is a bank or insurer (brokers and exchanges excluded)
- it is a mortgage lender or financial conglomerate
- it is an asset manager with assets above 20 × revenue
- total assets exceed 3.5 × revenue

The model:

```
ROE_t  = ROE_0 + (ROE_terminal − ROE_0) × t / N
RI_t   = (ROE_t − Ke) × B_{t−1}
B_t    = B_{t−1} × (1 + book growth)
Value  = B_0 + Σ RI_t / (1 + Ke)^t + [(ROE_terminal − Ke) × B_N / (Ke − g)] / (1 + Ke)^N
```

By default, excess returns decay halfway towards the cost of equity by year N. The justified price-to-book is `(ROE − g) / (Ke − g)`, and the ROE the market implies is `g + P/B × (Ke − g)`.

## Expectations Lab

The Expectations Lab turns the valuation around. Instead of estimating value from assumptions, it solves for the assumption that today's price already contains.

**Implied drivers.** Each driver is solved on its own, with every other input held at the analyst's scenario, so that the DCF equals the market price exactly. The solver runs a coarse grid scan to bracket every root, then refines with Brent's method, and prefers the root closest to the scenario. The drivers are:

- revenue growth: search range −30% to +60%
- target EBITDA margin: search range −20% to 90%
- terminal growth
- expected return: the discount rate that equates price and cash flows, akin to an internal rate of return

If no value in range reproduces the price, the driver is reported as out of reach rather than extrapolated.

**Break-even frontier.** For a sweep of growth rates, the margin required to justify the price is solved. The resulting curve is every (growth, margin) future that is worth exactly today's price. The company's actual fiscal years are plotted against it.

**Value landscape.** A 33 × 33 grid of value per share over growth and margin. In 3D it rises as a surface, and the market price is a glass plane cutting through it; the intersection is the frontier.

**Odds.** Correlated (growth, margin) outcomes are drawn around the scenario:

- volatility is the company's own historical standard deviation, bounded
- the correlation between growth and margin is +0.3

The odds are the share of outcomes worth more than the market price.

**Expectations gap and stance.** The gap is implied growth minus the historical CAGR. A gap above +5 points is labelled *priced for acceleration*, and one below −5 points *priced for slowdown*.

**Universe radar.** The same reverse DCF runs on every company in the dataset at its baseline assumptions, and the results are cached against a signature of the data. This produces cross-sectional views: the widest gaps, sector medians, and the priced-in versus delivered scatter.

## Trading comparables

**Peer selection.** Candidates come from the same sector and the same model family, so banks are compared with banks. Each candidate is scored:

```
score = 3 × same industry + 2 × same country − |ln(market cap_peer / market cap_target)|
```

Market caps are converted to USD at stored FX rates for the size term only. The top 12 candidates by score form the peer set.

**Multiples.**

- Operating companies: EV / EBITDA (the primary anchor), EV / Revenue and P / E.
- Balance-sheet financials: P / B (primary) and P / E.

Multiples are ratios within each company's own currency, so they compare cleanly across currencies. Values outside sensible bounds are set aside and counted:

- negative values
- EV / EBITDA above 60×
- EV / Revenue above 40×
- P / E above 100×
- P / B above 20×

**Implied value.** The 25th, 50th and 75th percentile peer multiples are applied to the target's own metric. For enterprise multiples, EV is bridged to equity with the target's own debt and cash. At least three valid peers are required.

## M&A accretion and dilution

All figures are expressed in the acquirer's currency. A target reporting in another currency is restated at the latest stored FX rate, and the rate and its date are disclosed.

```
Offer price        = target price × (1 + premium)
Purchase equity    = offer price × target shares
New shares         = stock consideration / acquirer price
Financing cost     = (new debt × debt rate + cash used × cash yield) × (1 − tax)
Synergies          = revenue synergies × incremental margin + cost synergies
Pro forma NI (Y1)  = NI_acq + NI_target − financing cost + synergies × (1 − tax) − integration × (1 − tax)
EPS accretion      = pro forma NI / (acquirer shares + new shares) ÷ standalone EPS − 1
```

The consideration mix of stock, cash on hand and new debt must sum to 100%. The model reports:

- **Break-even synergies:** the pre-tax synergies that make year-1 EPS neutral.
- **Ownership split:** how the combined company is owned.
- **Pro forma net debt / EBITDA:** combined leverage.
- **The P/E rule:** a stock deal is accretive before synergies when the acquirer's P/E exceeds the P/E paid.

## Leveraged buyout

**Sources and uses.**

- Entry EV = entry multiple × EBITDA_0.
- Transaction fees are a share of entry EV.
- Senior and subordinated debt are sized in turns of EBITDA and capped at 75% of EV.
- The sponsor contributes the remaining equity.

The baseline entry is a take-private at a 25% premium to market equity plus net debt, exiting at the same multiple.

**Cash waterfall.** Each year, levered free cash flow repays debt in this order:

1. Mandatory senior amortisation (5% a year).
2. The revolver.
3. A senior cash sweep.
4. A subordinated sweep.

Shortfalls are funded by a revolver priced at 75 bp below the senior rate.

**Returns.** Exit equity = exit EBITDA × exit multiple − net debt. MOIC = exit equity / sponsor equity, and IRR = `MOIC^(1/N) − 1`.

**Attribution.** Value created is split exactly into four parts, plus an equity-floor term when the exit equity would be negative. The parts sum to the gain by construction:

- EBITDA growth: EBITDA change × entry multiple
- multiple expansion: exit EBITDA × change in multiple
- deleveraging: reduction in net debt
- fees and leakage

**Stress test.** The analyst's own structure is re-run with each of these shocks, and then with all of them at once:

- debt costs +200 bp
- revenue growth −5 points
- exit margin −3 points
- exit multiple −2×

## Risk lab

**Value-at-Risk and Expected Shortfall.** One-day losses on daily returns at 95% and 99% confidence, estimated three ways:

- empirical quantiles
- a normal distribution
- a Cornish-Fisher expansion that adjusts the normal quantile for skewness and excess kurtosis

Ten-day figures use √10 scaling, which ignores volatility clustering. A Jarque-Bera test reports whether normality is rejected.

**Extreme value theory.** Losses above their 90th percentile are fitted to a Generalised Pareto distribution by maximum likelihood (peaks over threshold). The shape parameter ξ describes the tail:

- ξ > 0: heavy tails
- ξ ≈ 0: exponential tails
- ξ < 0: bounded tails

Tail VaR and ES are reported at 99%, 99.5% and 99.9%, with a Kolmogorov-Smirnov goodness-of-fit test.

**Volatility regimes.** A two-state Gaussian hidden Markov model is fitted to daily log returns:

- estimation uses Baum-Welch EM with scaled forward-backward recursions and five random starts
- current probabilities are filtered, meaning they use only data up to today
- the price chart shows smoothed probabilities
- BIC compares the model against a single normal distribution to report whether two regimes are supported

**Factor exposures.** Fama-French style factors are built separately for each market (US and India) from the stocks in the local universe. The stock being analysed is left out of its own factors.

- MKT is the cap-weighted market return minus the risk-free rate.
- SMB and HML come from a 2 × 3 sort on size and book-to-market.

The stock's excess returns are regressed on the three factors with Newey-West (HAC) standard errors. Limitations: sort characteristics are static, the universe is large-cap only, and the window is about one year.

**Merton distance to default.** Equity is treated as a call option on firm assets:

```
E = V N(d1) − D e^{−rT} N(d2)
σ_E E = N(d1) σ_V V
```

The two equations are solved jointly for asset value V and asset volatility σ_V:

- equity volatility is realised volatility
- the default point is total debt
- the horizon is one year

Distance to default = `(ln(V/D) + (r − σ_V²/2)T) / (σ_V √T)`. The probability of default is `N(−DD)`; it is risk-neutral and so overstates real-world default rates. The model is not meaningful for banks and insurers, and says so.

**Copulas.** Two stocks' returns are aligned by trading date and converted to pseudo-observations, `rank / (n + 1)`. Four copula families are fitted by maximum likelihood, and the lowest AIC wins:

- Gaussian: no tail dependence
- Student t: symmetric tail dependence
- Clayton: lower-tail dependence
- Gumbel: upper-tail dependence

The joint-crash probability is the chance that both fall below their own 5% quantile on the same day. It is compared with the empirical frequency and with independence.

**Monte Carlo valuation.** Revenue growth, target margin, WACC and terminal growth are drawn jointly from a multivariate normal around the scenario:

- growth and margin volatility are calibrated to the company's own history, bounded
- growth and margin are correlated +0.3
- WACC and terminal growth are correlated +0.5

Draws that would put terminal growth within 1% of WACC are pulled back. The model reports:

- the value distribution
- the probability that value lies below the market price
- a tornado of each input at its own 10th and 90th percentile
- a variance attribution from a standardised regression of value on the draws

**Valuation confidence.** A computed 0–100 score with published weights, renormalised over whichever components are available:

| Component | Weight |
|---|---|
| Data quality | 25% |
| Monte Carlo dispersion | 25% |
| Agreement between intrinsic and comps value | 20% |
| Terminal-value reliance | 15% |
| Evidence depth (years of history, days of prices) | 15% |

## Excel model and IC memo

**Excel model.** The workbook is built with live formulas, not pasted values. It contains:

- an assumptions sheet that drives the DCF or excess-return schedule
- the sensitivity grids
- the accretion and dilution model
- the LBO
- comps
- a checks sheet

The workbook's own checks sheet compares its formula results with the Python engines, to a relative tolerance of 10⁻⁶. The test suite recalculates the workbook with an independent formula engine and requires every check to pass.

**IC memo.** The memo is written from the same engine outputs for the current scenario. With an LLM key configured (Gemini first, then Groq), ValuAI drafts it. Without one, or if every provider fails, a deterministic analyst template writes it from the same numbers.

## ValuAI copilot

ValuAI receives a compact, factual context for the question it is asked:

- the company record
- the scenario and baseline
- the intrinsic value, expectations and comps
- health flags and risk metrics
- the page the analyst is on

It is instructed to answer only from that context. Answers stream over server-sent events, and providers are tried in order until one answers. If none is configured or every call fails, a rule-based offline analyst answers the common questions from the same context, so the copilot never goes silent.

## Limitations

- **Annual data only.** There are no quarterly or trailing-twelve-month figures, and fundamentals can be up to a year old.
- **About one year of daily prices.** Regressions, VaR, regimes and copulas are estimated on roughly 270 trading days.
- **Provider data.** Yahoo Finance data can contain errors; the quality engine catches identity breaks but not every misreport.
- **Share counts.** Shares outstanding are basic, not fully diluted.
- **No transaction comps.** Precedent-transaction multiples are not included, because no reliable free source exists. The endpoint reports this as `UNAVAILABLE`.
- **Market parameters.** Rates are static per currency, not a live yield curve.
- **Not investment advice.** ValuEngine is an analytical tool and not a recommendation to buy or sell any security.
