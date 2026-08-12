"""
Global Configuration & Default Parameters for M&A Accretion/Dilution & LBO Valuation Engine.
Institutional Wall Street Corporate Finance Defaults.
"""

import math
import numpy as np


def sanitize_val(val, fallback=0.0) -> float:
    """
    Sanitize mathematical values to prevent NaN/Inf React frontend canvas crashes.

    Parameters
    ----------
    val : Any
        Numerical value or object to sanitize.
    fallback : float
        Fallback return if value is None, NaN, or Inf.

    Returns
    -------
    float
        Sanitized float number.
    """
    if val is None:
        return float(fallback)
    try:
        fval = float(val)
        if math.isnan(fval) or math.isinf(fval) or np.isnan(fval) or np.isinf(fval):
            return float(fallback)
        return fval
    except (ValueError, TypeError):
        return float(fallback)


# Corporate & Market Tax / Rate Assumptions
CORPORATE_TAX_RATE: float = 0.21        # 21% US Federal Corporate Tax Rate
RISK_FREE_RATE: float = 0.042           # 4.2% 10-Year US Treasury Benchmark
MARKET_RISK_PREMIUM: float = 0.055      # 5.5% Equity Risk Premium (ERP)
DEFAULT_WACC: float = 0.085             # 8.5% Baseline Discount Rate
TERMINAL_GROWTH_RATE: float = 0.025     # 2.5% Perpetual Growth Rate

# Debt Capital Structure & Interest Rate Defaults
SENIOR_DEBT_INTEREST: float = 0.065     # 6.5% Senior Debt Annual Coupon
SUBORDINATED_DEBT_INTEREST: float = 0.090 # 9.0% Subordinated Debt Coupon
DEFAULT_COST_OF_DEBT: float = 0.055     # 5.5% Pre-tax Cost of Debt for WACC

# Valuation & Forecasting Assumptions
DEFAULT_PROJECTION_YEARS: int = 5
DEFAULT_REV_GROWTH: float = 0.07        # 7% Annual Revenue Growth
DEFAULT_EBITDA_MARGIN: float = 0.25     # 25% EBITDA Margin
DEFAULT_CAPEX_PCT_REV: float = 0.04     # 4% CapEx as % of Revenue
DEFAULT_NWC_PCT_REV: float = 0.02       # 2% Delta NWC as % of Revenue
DEFAULT_DA_PCT_REV: float = 0.04        # 4% D&A as % of Revenue

# LBO Default Parameters
DEFAULT_LBO_ENTRY_MULTIPLE: float = 10.0 # 10.0x Entry EV/EBITDA
DEFAULT_LBO_EXIT_MULTIPLE: float = 11.0  # 11.0x Exit EV/EBITDA
DEFAULT_SENIOR_DEBT_PCT: float = 0.40    # 40% Senior Debt / Entry EV
DEFAULT_SUB_DEBT_PCT: float = 0.20       # 20% Subordinated Debt / Entry EV

# M&A Default Parameters
DEFAULT_OFFER_PREMIUM: float = 0.25      # 25% Premium over Target Spot Price
DEFAULT_PCT_CASH: float = 0.50          # 50% Cash / Debt
DEFAULT_PCT_STOCK: float = 0.50         # 50% Stock Equity
DEFAULT_COST_SYNERGIES: float = 50_000_000 # $50M Cost Synergies

# Presets / Fallback Data for Popular Tickers (in case yfinance API is rate limited)
PRESET_FINANCIALS = {
    "AAPL": {
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "current_price": 225.00,
        "shares_outstanding": 15_200_000_000,
        "market_cap": 3_420_000_000_000,
        "revenue": 385_600_000_000,
        "ebitda": 130_000_000_000,
        "ebit": 115_000_000_000,
        "net_income": 100_000_000_000,
        "operating_cash_flow": 118_000_000_000,
        "capex": 11_500_000_000,
        "total_debt": 105_000_000_000,
        "cash_and_equivalents": 62_000_000_000,
        "book_equity": 74_000_000_000,
        "beta": 1.08,
        "d_and_a": 11_500_000_000
    },
    "MSFT": {
        "ticker": "MSFT",
        "company_name": "Microsoft Corporation",
        "current_price": 415.00,
        "shares_outstanding": 7_430_000_000,
        "market_cap": 3_083_000_000_000,
        "revenue": 245_000_000_000,
        "ebitda": 125_000_000_000,
        "ebit": 109_000_000_000,
        "net_income": 88_000_000_000,
        "operating_cash_flow": 118_500_000_000,
        "capex": 44_000_000_000,
        "total_debt": 75_000_000_000,
        "cash_and_equivalents": 78_000_000_000,
        "book_equity": 238_000_000_000,
        "beta": 0.90,
        "d_and_a": 16_000_000_000
    },
    "NVDA": {
        "ticker": "NVDA",
        "company_name": "NVIDIA Corporation",
        "current_price": 125.00,
        "shares_outstanding": 24_600_000_000,
        "market_cap": 3_075_000_000_000,
        "revenue": 96_000_000_000,
        "ebitda": 60_000_000_000,
        "ebit": 56_000_000_000,
        "net_income": 53_000_000_000,
        "operating_cash_flow": 55_000_000_000,
        "capex": 3_000_000_000,
        "total_debt": 11_000_000_000,
        "cash_and_equivalents": 31_000_000_000,
        "book_equity": 43_000_000_000,
        "beta": 1.68,
        "d_and_a": 4_000_000_000
    }
}

# UI / Report Styling Theme
NAVY_HEADER_HEX = "1B365D"
ACCENT_BLUE_HEX = "4A90E2"
ACCENT_GREEN_HEX = "2ECC71"
ACCENT_RED_HEX = "E74C3C"
LIGHT_GRAY_HEX = "F8F9FA"
