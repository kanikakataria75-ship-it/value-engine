"""Factor exposures against factors built from the local universe.

For each market (USD-listed and INR-listed stocks separately) daily factors are constructed
Fama-French style from the stocks in the local store:
  MKT  cap-weighted market return minus the daily risk-free rate
  SMB  small minus big: average of the three small portfolios minus the three big ones
  HML  high minus low book-to-market: average of the two value portfolios minus the two growth ones
using a 2 x 3 sort on market cap (median) and book-to-market (30th / 70th percentiles) with
cap-weighted portfolios. The stock being analysed is removed from its own factors (leave-one-out).

Limitations (disclosed in every response): sort characteristics are static (latest fiscal year,
so there is look-ahead), the universe is large-cap only, and the window is about one year.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from ...config import market_parameters

MIN_COVERAGE = 0.7
GROUPS = ("ALL", "SL", "SM", "SH", "BL", "BM", "BH")


def build_price_panel(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows, columns=["ticker", "date", "close"])
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.pivot_table(index="date", columns="ticker", values="close", aggfunc="last").sort_index()


def ols_hac(y: np.ndarray, X: np.ndarray, maxlags: int = 5) -> dict[str, np.ndarray | float]:
    """OLS with Newey-West (Bartlett kernel) heteroskedasticity- and autocorrelation-consistent standard errors."""
    n, k = X.shape
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    resid = y - X @ beta
    u = X * resid[:, None]
    s = u.T @ u
    for lag in range(1, maxlags + 1):
        weight = 1 - lag / (maxlags + 1)
        gamma = u[lag:].T @ u[:-lag]
        s += weight * (gamma + gamma.T)
    cov = xtx_inv @ s @ xtx_inv
    se = np.sqrt(np.diag(cov))
    t = beta / se
    sst = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - float(resid @ resid) / sst if sst > 0 else 0.0
    return {"beta": beta, "se": se, "t": t, "p": 2 * (1 - stats.norm.cdf(np.abs(t))), "resid": resid,
            "r2": r2, "adj_r2": 1 - (1 - r2) * (n - 1) / (n - k)}


@dataclass
class MarketData:
    returns: pd.DataFrame        # dates x constituents (simple returns)
    weights: pd.Series           # static market caps
    group_of: dict[str, str]     # ticker -> style portfolio (SL..BH) or "" if unsorted
    numerators: dict[str, pd.Series]
    denominators: dict[str, pd.Series]
    rf_daily: float
    portfolio_sizes: dict[str, int]


class FactorModel:
    """Holds the universe return panel and pre-aggregated portfolio sums for fast leave-one-out factors."""

    def __init__(self, panel: pd.DataFrame, companies: dict[str, dict[str, Any]]) -> None:
        self.returns = panel.pct_change(fill_method=None) if not panel.empty else panel
        self.companies = companies
        self._markets: dict[str, MarketData] = {}

    def _market(self, currency: str) -> MarketData:
        if currency in self._markets:
            return self._markets[currency]
        tickers = [t for t in self.returns.columns if (self.companies.get(t, {}).get("currency") or "USD").upper() == currency]
        caps = pd.Series({t: self.companies[t].get("market_cap") or 0.0 for t in tickers}, dtype=float)
        caps = caps[caps > 0]
        returns = self.returns[caps.index]
        returns = returns[returns.notna().mean(axis=1) >= MIN_COVERAGE]
        book = pd.Series({t: self.companies[t].get("book_equity") for t in caps.index}, dtype=float)
        bm = (book / caps)[book > 0]
        size_cut = caps.median()
        low_cut, high_cut = bm.quantile(0.3), bm.quantile(0.7)
        group_of: dict[str, str] = {}
        for t in caps.index:
            if t not in bm.index:
                group_of[t] = ""
                continue
            size = "S" if caps[t] <= size_cut else "B"
            style = "L" if bm[t] <= low_cut else "H" if bm[t] >= high_cut else "M"
            group_of[t] = size + style
        filled = returns.fillna(0.0)
        mask = returns.notna().astype(float)
        numerators, denominators = {}, {}
        for group in GROUPS:
            members = list(caps.index) if group == "ALL" else [t for t, g in group_of.items() if g == group]
            w = caps[members]
            numerators[group] = filled[members].mul(w, axis=1).sum(axis=1)
            denominators[group] = mask[members].mul(w, axis=1).sum(axis=1)
        data = MarketData(returns, caps, group_of, numerators, denominators,
                          market_parameters(currency).risk_free_rate / 252,
                          {g: sum(1 for x in group_of.values() if x == g) for g in GROUPS[1:]})
        self._markets[currency] = data
        return data

    def factors(self, currency: str, exclude: str | None = None) -> tuple[pd.DataFrame, MarketData]:
        md = self._market(currency)
        nums = dict(md.numerators)
        dens = dict(md.denominators)
        if exclude and exclude in md.weights.index:
            w = md.weights[exclude]
            r = md.returns[exclude]
            contribution, present = r.fillna(0.0) * w, r.notna().astype(float) * w
            for group in ("ALL", md.group_of.get(exclude, "")):
                if group:
                    nums[group] = nums[group] - contribution
                    dens[group] = dens[group] - present
        port = {g: nums[g] / dens[g].replace(0, np.nan) for g in GROUPS}
        frame = pd.DataFrame({
            "MKT": port["ALL"] - md.rf_daily,
            "SMB": (port["SL"] + port["SM"] + port["SH"]) / 3 - (port["BL"] + port["BM"] + port["BH"]) / 3,
            "HML": (port["SH"] + port["BH"]) / 2 - (port["SL"] + port["BL"]) / 2,
        }).dropna()
        return frame, md

    def regression_beta(self, ticker: str, currency: str) -> float | None:
        """CAPM beta against the leave-one-out local market index (Blume-adjusted toward 1).

        Pure numpy on the pre-aggregated market sums, so the whole universe can be processed quickly.
        """
        symbol = ticker.upper()
        md = self._market(currency)
        if symbol not in md.weights.index:
            return None
        stock = md.returns[symbol].to_numpy()
        present = ~np.isnan(stock)
        w = float(md.weights[symbol])
        numerator = md.numerators["ALL"].to_numpy() - np.where(present, stock, 0.0) * w
        denominator = md.denominators["ALL"].to_numpy() - present * w
        with np.errstate(invalid="ignore", divide="ignore"):
            market = numerator / denominator
        valid = present & np.isfinite(market)
        if valid.sum() < 120:
            return None
        x, y = market[valid], stock[valid]
        raw = float(np.cov(x, y, ddof=1)[0, 1] / np.var(x, ddof=1))
        return 0.67 * raw + 0.33

    def regression(self, ticker: str, company: dict[str, Any]) -> dict[str, Any]:
        symbol = ticker.upper()
        if symbol not in self.returns.columns:
            return {"status": "UNAVAILABLE", "message": "No price history for this ticker in the local store."}
        currency = (company.get("currency") or "USD").upper()
        factors, md = self.factors(currency, exclude=symbol)
        data = factors.join(self.returns[symbol].rename("stock"), how="inner").dropna()
        constituents = int(len(md.weights))
        if len(data) < 120 or constituents < 30:
            return {"status": "UNAVAILABLE",
                    "message": f"Insufficient data for factor regression ({len(data)} days, {constituents} constituents)."}
        y = data["stock"].to_numpy() - md.rf_daily
        three = ols_hac(y, np.column_stack([np.ones(len(data)), data[["MKT", "SMB", "HML"]].to_numpy()]))
        capm = ols_hac(y, np.column_stack([np.ones(len(data)), data["MKT"].to_numpy()]))
        labels = [("const", "Alpha (daily)"), ("MKT", "Market (MKT-RF)"), ("SMB", "Size (SMB)"), ("HML", "Value (HML)")]
        coefficients = [
            {"factor": key, "label": label, "coefficient": float(three["beta"][i]), "std_error": float(three["se"][i]),
             "t_stat": float(three["t"][i]), "p_value": float(three["p"][i])}
            for i, (key, label) in enumerate(labels)
        ]
        cumulative = (1 + pd.DataFrame({"stock": data["stock"], "market": data["MKT"] + md.rf_daily})).cumprod()
        return {
            "status": "VALID",
            "market": "India (NSE) large caps in the local store" if currency == "INR" else "US large caps in the local store",
            "observations": int(len(data)),
            "start_date": str(data.index[0].date()),
            "end_date": str(data.index[-1].date()),
            "coefficients": coefficients,
            "alpha_annualized": float(three["beta"][0] * 252),
            "r_squared": float(three["r2"]),
            "adjusted_r_squared": float(three["adj_r2"]),
            "residual_volatility_annualized": float(np.std(three["resid"], ddof=4) * math.sqrt(252)),
            "capm_beta": float(capm["beta"][1]),
            "capm_beta_std_error": float(capm["se"][1]),
            "capm_r_squared": float(capm["r2"]),
            "provider_beta": company.get("beta"),
            "universe": {"constituents": constituents, "portfolio_sizes": md.portfolio_sizes, "rf_daily": md.rf_daily},
            "cumulative": [{"date": str(d.date()), "stock": float(r.stock), "market": float(r.market)}
                           for d, r in cumulative.iterrows()],
            "methodology": "Daily excess returns regressed on MKT, SMB and HML factors built from the local universe "
                           "(2x3 cap-weighted sorts, stock excluded); Newey-West (5 lag) standard errors.",
            "limitations": "Static sort characteristics (latest fiscal year, look-ahead), large-cap universe, ~1 year window.",
        }
