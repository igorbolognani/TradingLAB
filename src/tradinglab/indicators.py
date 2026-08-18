"""Pure causal indicators on the normalized Close contract."""

import numpy as np
import pandas as pd


def simple_moving_average(close: pd.Series, lookback: int) -> pd.Series:
    """Arithmetic mean with explicit full-window warm-up."""

    if lookback < 1:
        raise ValueError("lookback must be positive")
    return close.astype(float).rolling(window=lookback, min_periods=lookback).mean()


def population_zscore(close: pd.Series, lookback: int) -> pd.Series:
    """Rolling population z-score; zero volatility is deterministically unavailable."""

    if lookback < 1:
        raise ValueError("lookback must be positive")
    values = close.astype(float)
    rolling = values.rolling(window=lookback, min_periods=lookback)
    mean = rolling.mean()
    std = rolling.std(ddof=0)
    result = (values - mean) / std
    return result.mask((std == 0) | ~np.isfinite(result), np.nan)


def indicator_series(
    close: pd.Series, strategy_id: str, parameters: dict[str, float | int]
) -> pd.Series:
    """Map a canonical strategy identifier to its one declared indicator."""

    if strategy_id == "TREND_SMA200_V1":
        return simple_moving_average(close, int(parameters["sma"])).rename("indicator")
    if strategy_id == "MEANREV_Z20_V1":
        return population_zscore(close, int(parameters["lookback"])).rename("indicator")
    return pd.Series(np.nan, index=close.index, name="indicator", dtype=float)
