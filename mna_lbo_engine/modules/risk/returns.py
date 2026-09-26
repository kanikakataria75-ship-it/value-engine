"""Price-to-return transformations with explicit date alignment."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

MIN_OBSERVATIONS = 60


class InsufficientData(ValueError):
    pass


def price_series(prices: list[dict[str, Any]] | None) -> pd.Series:
    rows = [(p.get("date"), p.get("close")) for p in (prices or []) if p.get("date") and p.get("close")]
    if not rows:
        return pd.Series(dtype=float)
    series = pd.Series({str(d)[:10]: float(c) for d, c in rows}, dtype=float)
    series.index = pd.to_datetime(series.index)
    series = series[series > 0].sort_index()
    return series[~series.index.duplicated(keep="last")]


def simple_returns(prices: list[dict[str, Any]] | None, minimum: int = MIN_OBSERVATIONS) -> pd.Series:
    returns = price_series(prices).pct_change().dropna()
    if len(returns) < minimum:
        raise InsufficientData(f"Only {len(returns)} daily returns available; at least {minimum} are required.")
    return returns


def log_returns(prices: list[dict[str, Any]] | None, minimum: int = MIN_OBSERVATIONS) -> pd.Series:
    returns = np.log(price_series(prices)).diff().dropna()
    if len(returns) < minimum:
        raise InsufficientData(f"Only {len(returns)} daily returns available; at least {minimum} are required.")
    return returns


def aligned_log_returns(prices_a: list[dict[str, Any]], prices_b: list[dict[str, Any]],
                        minimum: int = MIN_OBSERVATIONS) -> pd.DataFrame:
    """Inner-join two price histories on trading date before differencing.

    Returns are computed between consecutive *common* dates, so markets with different holiday
    calendars (e.g. NYSE vs. NSE) are paired correctly.
    """
    joined = pd.concat({"a": price_series(prices_a), "b": price_series(prices_b)}, axis=1, join="inner")
    frame = np.log(joined).diff().dropna()
    if len(frame) < minimum:
        raise InsufficientData(f"Only {len(frame)} overlapping trading days; at least {minimum} are required.")
    return frame


def max_drawdown(prices: list[dict[str, Any]]) -> dict[str, Any]:
    series = price_series(prices)
    if series.empty:
        return {"max_drawdown": None}
    running_max = series.cummax()
    drawdown = series / running_max - 1.0
    trough = drawdown.idxmin()
    peak = series.loc[:trough].idxmax()
    return {"max_drawdown": float(drawdown.min()), "peak_date": str(peak.date()), "trough_date": str(trough.date())}
