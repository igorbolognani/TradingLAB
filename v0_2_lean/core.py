"""Small independent V0.2 daily replay used by LEAN validation fixtures.

The replay is intentionally separate from the V0.1 package.  It provides a
deterministic oracle for the LEAN algorithm's exported events and makes the
six V0.2 acceptance dimensions testable without network access or Docker.
"""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import mean, stdev

from .contract import (
    ANNUALIZATION_SESSIONS,
    INITIAL_CASH,
    PRIMARY_PARAMETERS,
    RISK_FREE_RATE,
    SPLITS,
)


@dataclass(frozen=True)
class Bar:
    session: date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Signal:
    decision_session: date
    order_eligibility_session: date
    action: str
    reason: str
    indicator_value: float | None


@dataclass(frozen=True)
class Fill:
    session: date
    side: str
    quantity: int
    price: float
    cost: float
    reason: str


@dataclass(frozen=True)
class EquityPoint:
    session: date
    cash: float
    quantity: int
    close: float
    gross_equity: float
    cumulative_costs: float
    net_equity: float


@dataclass(frozen=True)
class ReplayResult:
    strategy_id: str
    asset: str
    split: str
    friction_bps: int
    parameters: dict[str, float | int]
    signals: tuple[Signal, ...]
    fills: tuple[Fill, ...]
    equity: tuple[EquityPoint, ...]
    metrics: dict[str, float | int | None]


def load_normalized_csv(path: Path) -> list[Bar]:
    """Load only the normalized V0.1 CSV contract, never raw provider rows."""

    result: list[Bar] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            result.append(
                Bar(
                    session=date.fromisoformat(row["Session"][:10]),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row["Volume"]),
                )
            )
    if not result or result != sorted(result, key=lambda item: item.session):
        raise ValueError(f"normalized bars are not chronological: {path}")
    if len({item.session for item in result}) != len(result):
        raise ValueError(f"normalized bars contain duplicate sessions: {path}")
    return result


def _sma(values: list[float], index: int, window: int) -> float | None:
    if index + 1 < window:
        return None
    return mean(values[index + 1 - window : index + 1])


def _zscore(values: list[float], index: int, window: int) -> float | None:
    if index + 1 < window:
        return None
    sample = values[index + 1 - window : index + 1]
    average = mean(sample)
    deviation = math.sqrt(mean((value - average) ** 2 for value in sample))
    if deviation == 0:
        return None
    return (values[index] - average) / deviation


def _next_session(bars: list[Bar], index: int) -> date | None:
    return bars[index + 1].session if index + 1 < len(bars) else None


def _metrics(
    equity: list[EquityPoint], fills: list[Fill], initial_cash: float
) -> dict[str, float | int | None]:
    net = [point.net_equity for point in equity]
    if not net:
        raise ValueError("replay produced no evaluation sessions")
    # Match the V0.1 canonical convention: the first evaluation close is
    # compared with the initial cash base, so the return series has one value
    # per evaluation session.  CAGR uses the same session-row count.
    returns = [net[0] / initial_cash - 1]
    returns.extend(net[index] / net[index - 1] - 1 for index in range(1, len(net)))
    observations = len(net)
    total_return = net[-1] / initial_cash - 1
    cagr = (
        (net[-1] / initial_cash) ** (ANNUALIZATION_SESSIONS / observations) - 1
        if observations
        else None
    )
    volatility = (
        stdev(returns) * math.sqrt(ANNUALIZATION_SESSIONS)
        if len(returns) >= 2
        else None
    )
    sharpe = (
        (mean(returns) - RISK_FREE_RATE / ANNUALIZATION_SESSIONS)
        / stdev(returns)
        * math.sqrt(ANNUALIZATION_SESSIONS)
        if len(returns) >= 2 and stdev(returns) != 0
        else None
    )
    running_max = net[0]
    drawdowns: list[float] = []
    for value in net:
        running_max = max(running_max, value)
        drawdowns.append(value / running_max - 1)
    costs = sum(fill.cost for fill in fills)
    gross_final = net[-1] + costs
    gross_to_net = gross_final / initial_cash - 1 - total_return
    mean_equity = mean(net)
    turnover = (
        sum(abs(fill.quantity * fill.price) for fill in fills) / mean_equity
        if mean_equity
        else None
    )
    return {
        "total_return": total_return,
        "CAGR": cagr,
        "annualized_volatility": volatility,
        "Sharpe": sharpe,
        "max_drawdown": min(drawdowns),
        "exposure": mean(point.quantity != 0 for point in equity),
        "turnover": turnover,
        "number_of_trades": sum(fill.side == "entry" for fill in fills),
        "modeled_costs": costs,
        "gross_to_net_cost_drag": gross_to_net,
    }


def replay(
    bars: Iterable[Bar],
    *,
    asset: str,
    split: str,
    strategy_id: str,
    friction_bps: int,
    parameters: dict[str, float | int] | None = None,
) -> ReplayResult:
    """Replay one declared V0.2 configuration using explicit next-open fills."""

    rows = list(bars)
    if split not in SPLITS:
        raise ValueError(f"unknown split: {split}")
    params = dict(parameters or PRIMARY_PARAMETERS[strategy_id])
    start, end = SPLITS[split]
    eval_indices = [
        index for index, bar in enumerate(rows) if start <= bar.session <= end
    ]
    if not eval_indices:
        raise ValueError(f"no bars in split {split}")
    eval_start = eval_indices[0]
    eval_end = eval_indices[-1]
    close_values = [bar.close for bar in rows]
    cash = INITIAL_CASH
    quantity = 0
    held_sessions = 0
    cumulative_costs = 0.0
    pending: tuple[str, str, float | None] | None = None
    signals: list[Signal] = []
    fills: list[Fill] = []
    equity: list[EquityPoint] = []

    for index, bar in enumerate(rows):
        if index > eval_end:
            break
        # A decision made after close t is eligible only at the next valid row.
        if pending is not None and index in eval_indices:
            action, reason, _indicator = pending
            if action == "enter" and quantity == 0:
                rate = friction_bps / 10_000
                cost_per_share = bar.open * (1 + rate)
                buy_quantity = math.floor(cash / cost_per_share)
                if buy_quantity > 0:
                    cost = buy_quantity * bar.open * rate
                    cash -= buy_quantity * bar.open + cost
                    quantity = buy_quantity
                    held_sessions = 1
                    cumulative_costs += cost
                    fills.append(
                        Fill(bar.session, "entry", buy_quantity, bar.open, cost, reason)
                    )
            elif action == "exit" and quantity > 0:
                cost = quantity * bar.open * friction_bps / 10_000
                cash += quantity * bar.open - cost
                fills.append(
                    Fill(bar.session, "exit", quantity, bar.open, cost, reason)
                )
                cumulative_costs += cost
                quantity = 0
                held_sessions = 0
            pending = None

        if index in eval_indices:
            if quantity > 0 and fills and fills[-1].session != bar.session:
                held_sessions += 1
            net_equity = cash + quantity * bar.close
            equity.append(
                EquityPoint(
                    session=bar.session,
                    cash=cash,
                    quantity=quantity,
                    close=bar.close,
                    gross_equity=net_equity + cumulative_costs,
                    cumulative_costs=cumulative_costs,
                    net_equity=net_equity,
                )
            )

        decision_index = index >= max(0, eval_start - 1) and index < eval_end
        if not decision_index or pending is not None:
            continue
        next_session = _next_session(rows, index)
        if next_session is None or next_session > end:
            continue

        if strategy_id == "CASH_0_V1":
            continue
        if strategy_id == "BUY_HOLD_V1":
            if quantity == 0 and index == eval_start - 1:
                pending = ("enter", "first_eligible_open", None)
                signals.append(
                    Signal(
                        bar.session, next_session, "enter", "first_eligible_open", None
                    )
                )
            continue

        if strategy_id == "TREND_SMA200_V1":
            value = _sma(close_values, index, int(params["sma"]))
            if value is not None:
                target_long = bar.close > value
                if target_long and quantity == 0:
                    pending = ("enter", "close_above_sma", value)
                    signals.append(
                        Signal(
                            bar.session, next_session, "enter", "close_above_sma", value
                        )
                    )
                elif not target_long and quantity > 0:
                    pending = ("exit", "close_at_or_below_sma", value)
                    signals.append(
                        Signal(
                            bar.session,
                            next_session,
                            "exit",
                            "close_at_or_below_sma",
                            value,
                        )
                    )
            continue

        if strategy_id == "MEANREV_Z20_V1":
            value = _zscore(close_values, index, int(params["lookback"]))
            if (
                quantity == 0
                and value is not None
                and value <= float(params["entry_z"])
            ):
                pending = ("enter", "zscore_entry", value)
                signals.append(
                    Signal(bar.session, next_session, "enter", "zscore_entry", value)
                )
            elif quantity > 0:
                if value is not None and value >= float(params["exit_z"]):
                    pending = ("exit", "zscore_exit", value)
                    signals.append(
                        Signal(bar.session, next_session, "exit", "zscore_exit", value)
                    )
                elif held_sessions >= int(params["max_hold"]):
                    pending = ("exit", "max_hold_exit", value)
                    signals.append(
                        Signal(
                            bar.session,
                            next_session,
                            "exit",
                            "max_hold_exit",
                            value,
                        )
                    )
            continue
        raise ValueError(f"unknown strategy: {strategy_id}")

    return ReplayResult(
        strategy_id=strategy_id,
        asset=asset,
        split=split,
        friction_bps=friction_bps,
        parameters=params,
        signals=tuple(signals),
        fills=tuple(fills),
        equity=tuple(equity),
        metrics=_metrics(equity, fills, INITIAL_CASH),
    )


def parameters_json(parameters: dict[str, float | int]) -> str:
    return json.dumps(parameters, sort_keys=True, separators=(",", ":"))
