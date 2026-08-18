"""Canonical engine-independent metrics and matching benchmark deltas."""

import math
from typing import Any

import numpy as np
import pandas as pd

from tradinglab.constants import (
    ANNUALIZATION_SESSIONS,
    INITIAL_CASH,
    RISK_FREE_RATE,
)

METRIC_NAMES: tuple[str, ...] = (
    "total_return",
    "CAGR",
    "annualized_volatility",
    "Sharpe",
    "max_drawdown",
    "exposure",
    "turnover",
    "number_of_trades",
    "modeled_costs",
    "gross_to_net_cost_drag",
)


def _finite_or_none(value: float) -> float | None:
    return float(value) if math.isfinite(value) else None


def canonical_metrics(
    equity_curve: pd.DataFrame, trades: pd.DataFrame
) -> dict[str, float | int | None]:
    """Calculate exactly the documented V0.1 net-equity metrics."""

    if equity_curve.empty:
        raise ValueError("canonical metrics require an evaluation equity curve")
    net = equity_curve["net_equity"].astype(float)
    gross = equity_curve["gross_equity"].astype(float)
    observations = len(net)
    return_values = np.diff(
        np.concatenate(([INITIAL_CASH], net.to_numpy()))
    ) / np.concatenate(([INITIAL_CASH], net.to_numpy()[:-1]))
    total_return = float(net.iloc[-1] / INITIAL_CASH - 1)
    cagr = float(
        (net.iloc[-1] / INITIAL_CASH) ** (ANNUALIZATION_SESSIONS / observations) - 1
    )
    if observations < 2:
        volatility = None
        sharpe = None
    else:
        sample_std = float(np.std(return_values, ddof=1))
        volatility = _finite_or_none(sample_std * math.sqrt(ANNUALIZATION_SESSIONS))
        sharpe = (
            None
            if sample_std == 0
            else _finite_or_none(
                float(np.mean(return_values) - RISK_FREE_RATE / ANNUALIZATION_SESSIONS)
                / sample_std
                * math.sqrt(ANNUALIZATION_SESSIONS)
            )
        )
    augmented = pd.Series(np.concatenate(([INITIAL_CASH], net.to_numpy())), dtype=float)
    drawdown = augmented / augmented.cummax() - 1
    fill_notional = (
        float(trades["fill_notional"].abs().sum()) if not trades.empty else 0.0
    )
    modeled_costs = float(trades["modeled_friction"].sum()) if not trades.empty else 0.0
    number_of_trades = (
        int(trades.loc[trades["side"] == "buy", "lifecycle_id"].nunique())
        if not trades.empty
        else 0
    )
    gross_return = float(gross.iloc[-1] / INITIAL_CASH - 1)
    return {
        "total_return": total_return,
        "CAGR": cagr,
        "annualized_volatility": volatility,
        "Sharpe": sharpe,
        "max_drawdown": float(drawdown.min()),
        "exposure": float(equity_curve["exposure_state"].astype(float).mean()),
        "turnover": float(fill_notional / net.mean()),
        "number_of_trades": number_of_trades,
        "modeled_costs": modeled_costs,
        "gross_to_net_cost_drag": gross_return - total_return,
    }


def benchmark_deltas(
    strategy: dict[str, Any], buy_hold: dict[str, Any]
) -> dict[str, float | None]:
    """Compare only canonical metrics with the matching-asset Buy & Hold trial."""

    result: dict[str, float | None] = {}
    for name in ("CAGR", "Sharpe", "max_drawdown"):
        left = strategy.get(name)
        right = buy_hold.get(name)
        key = f"delta_{name}_vs_buy_hold"
        result[key] = None if left is None or right is None else float(left - right)
    return result
