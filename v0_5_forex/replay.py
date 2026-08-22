"""Minimal causal Forex replay for a first EURUSD D1 research pilot."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from statistics import fmean

from v0_5_forex.contract import ForexBar


@dataclass(frozen=True, slots=True)
class ForexSignal:
    decision_timestamp_utc: datetime
    eligible_timestamp_utc: datetime
    action: str
    sma_value: float


@dataclass(frozen=True, slots=True)
class ForexFill:
    timestamp_utc: datetime
    side: str
    quantity: int
    price: float
    modeled_cost: float


@dataclass(frozen=True, slots=True)
class ForexReplay:
    strategy_id: str
    signals: tuple[ForexSignal, ...]
    fills: tuple[ForexFill, ...]
    final_cash: float
    final_quantity: int
    final_equity: float


def replay_trend_sma(
    bars: list[ForexBar] | tuple[ForexBar, ...],
    *,
    sma_window: int = 200,
    initial_cash: float = 100_000.0,
    friction_bps: float = 5.0,
) -> ForexReplay:
    """Run long/cash Trend SMA on UTC bars with next-bar-open fills.

    This is intentionally a separate Forex research family.  It does not
    modify or reuse the frozen XNYS V0.1 strategies, and it creates no MT5
    connection or order request.
    """

    rows = tuple(bars)
    if not rows:
        raise ValueError("Forex replay requires at least one bar")
    if sma_window < 2:
        raise ValueError("sma_window must be at least two")
    if not math.isfinite(initial_cash) or initial_cash <= 0:
        raise ValueError("initial_cash must be finite and positive")
    if not math.isfinite(friction_bps) or friction_bps < 0:
        raise ValueError("friction_bps must be finite and non-negative")
    for bar in rows:
        bar.validate()
    if tuple(bar.timestamp_utc for bar in rows) != tuple(
        sorted(bar.timestamp_utc for bar in rows)
    ):
        raise ValueError("Forex replay bars must be chronological")

    cash = initial_cash
    quantity = 0
    pending: tuple[str, float] | None = None
    signals: list[ForexSignal] = []
    fills: list[ForexFill] = []
    rate = friction_bps / 10_000

    for index, bar in enumerate(rows):
        if pending is not None:
            action, _sma_value = pending
            if action == "enter" and quantity == 0:
                buy_quantity = math.floor(cash / (bar.open * (1 + rate)))
                if buy_quantity > 0:
                    cost = buy_quantity * bar.open * rate
                    cash -= buy_quantity * bar.open + cost
                    quantity = buy_quantity
                    fills.append(
                        ForexFill(
                            bar.timestamp_utc,
                            "buy",
                            buy_quantity,
                            bar.open,
                            cost,
                        )
                    )
            elif action == "exit" and quantity > 0:
                cost = quantity * bar.open * rate
                cash += quantity * bar.open - cost
                fills.append(
                    ForexFill(bar.timestamp_utc, "sell", quantity, bar.open, cost)
                )
                quantity = 0
            pending = None

        if index + 1 < sma_window or index + 1 >= len(rows):
            continue
        sma_value = fmean(row.close for row in rows[index + 1 - sma_window : index + 1])
        wants_long = bar.close > sma_value
        if wants_long and quantity == 0:
            pending = ("enter", sma_value)
            signals.append(
                ForexSignal(
                    bar.timestamp_utc,
                    rows[index + 1].timestamp_utc,
                    "enter",
                    sma_value,
                )
            )
        elif not wants_long and quantity > 0:
            pending = ("exit", sma_value)
            signals.append(
                ForexSignal(
                    bar.timestamp_utc,
                    rows[index + 1].timestamp_utc,
                    "exit",
                    sma_value,
                )
            )

    final_equity = cash + quantity * rows[-1].close
    return ForexReplay(
        strategy_id="FOREX_TREND_SMA200_RESEARCH_V1",
        signals=tuple(signals),
        fills=tuple(fills),
        final_cash=cash,
        final_quantity=quantity,
        final_equity=final_equity,
    )
