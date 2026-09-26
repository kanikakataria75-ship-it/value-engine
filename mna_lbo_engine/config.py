"""Global configuration for the ValuEngine financial engines.

Every market-level default lives here, keyed by trading currency, so that US and
Indian companies are never valued with each other's rates, taxes or growth anchors.
All values are editable assumptions, not facts; the UI shows where each one comes from.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class MarketParameters:
    currency: str
    country: str
    risk_free_rate: float           # 10-year government bond yield
    equity_risk_premium: float      # mature-market ERP plus country risk premium
    credit_spread: float            # default pre-tax spread over the risk-free rate for corporate debt
    tax_rate: float                 # statutory corporate tax rate
    terminal_growth: float          # default perpetual growth for DCF terminal values
    growth_anchor: float            # long-run nominal growth used to shrink historical growth rates
    source_note: str

    def as_dict(self) -> dict:
        return asdict(self)


MARKET_PARAMETERS: dict[str, MarketParameters] = {
    "USD": MarketParameters(
        currency="USD",
        country="United States",
        risk_free_rate=0.042,
        equity_risk_premium=0.055,
        credit_spread=0.015,
        tax_rate=0.21,
        terminal_growth=0.025,
        growth_anchor=0.05,
        source_note="US 10Y Treasury ~4.2%, mature-market ERP 5.5%, 21% federal corporate tax.",
    ),
    "INR": MarketParameters(
        currency="INR",
        country="India",
        risk_free_rate=0.065,
        equity_risk_premium=0.070,
        credit_spread=0.020,
        tax_rate=0.2517,
        terminal_growth=0.050,
        growth_anchor=0.10,
        source_note="India 10Y G-Sec ~6.5%, ERP 7.0% incl. country risk, 25.17% corporate tax (new regime).",
    ),
}

DEFAULT_CURRENCY = "USD"


def market_parameters(currency: str | None) -> MarketParameters:
    """Market defaults for a trading currency (falls back to USD for unknown currencies)."""
    return MARKET_PARAMETERS.get((currency or DEFAULT_CURRENCY).upper(), MARKET_PARAMETERS[DEFAULT_CURRENCY])


# --- Operating-model defaults (used only where company data cannot inform them) ---
DEFAULT_PROJECTION_YEARS = 5
DEFAULT_NWC_PCT_OF_INCREMENTAL_REVENUE = 0.05   # no working-capital lines exist in the dataset
GROWTH_HISTORY_WEIGHT = 0.6                     # weight on historical CAGR vs. the market growth anchor
BASELINE_GROWTH_BOUNDS = (-0.05, 0.25)
BETA_BOUNDS = (0.3, 3.0)
RONIC_CAP = 0.40                                # cap on return on new invested capital in terminal value

# --- LBO defaults ---
LBO_SENIOR_SPREAD = 0.0375
LBO_SUB_SPREAD = 0.060
LBO_DEFAULT_SENIOR_TURNS = 4.0
LBO_DEFAULT_SUB_TURNS = 1.5
LBO_MAX_DEBT_TO_EV = 0.75
LBO_DEFAULT_FEES_PCT = 0.02
LBO_TAKE_PRIVATE_PREMIUM = 0.25
LBO_SENIOR_AMORTIZATION = 0.05                  # mandatory annual amortisation, % of original senior debt

# --- M&A defaults ---
MNA_DEFAULT_PREMIUM = 0.25

# --- Excel report styling ---
NAVY_HEADER_HEX = "1B365D"
INPUT_BLUE_HEX = "1F4E9C"
LIGHT_GRAY_HEX = "F2F4F7"
