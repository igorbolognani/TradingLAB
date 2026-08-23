"""Data-frame boundary for the V0.6 reference portfolio replay.

The replay itself stays independent from providers and the local dashboard.
This module is the small, explicit boundary that converts a validated
normalized snapshot into the engine-independent ``PortfolioBar`` contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

import pandas as pd

from .contract import (
    AllocationMethod,
    PortfolioBar,
    PortfolioDecision,
    PortfolioResult,
)
from .replay import build_trend_decisions, replay_portfolio


@dataclass(frozen=True, slots=True)
class PortfolioRun:
    """A reproducible V0.6 run and the decisions that produced it."""

    result: PortfolioResult
    decisions: tuple[PortfolioDecision, ...]


def frames_to_portfolio_bars(
    frames: Mapping[str, pd.DataFrame],
) -> dict[str, tuple[PortfolioBar, ...]]:
    """Convert normalized OHLC frames into aligned portfolio bars."""

    if not frames:
        raise ValueError("portfolio requires at least one normalized frame")
    bars: dict[str, tuple[PortfolioBar, ...]] = {}
    for symbol, frame in frames.items():
        required = {"Open", "Close"}
        if not required.issubset(frame.columns):
            raise ValueError(f"portfolio frame is missing columns for {symbol}")
        if not isinstance(frame.index, pd.DatetimeIndex):
            raise ValueError(f"portfolio frame index is not datetime for {symbol}")
        rows = tuple(
            PortfolioBar(
                session=pd.Timestamp(cast(Any, timestamp)).date(),
                symbol=symbol,
                open=float(row["Open"]),
                close=float(row["Close"]),
            )
            for timestamp, row in frame.iterrows()
        )
        bars[symbol] = rows
    return bars


def run_trend_portfolio(
    frames: Mapping[str, pd.DataFrame],
    *,
    evaluation_start: date,
    evaluation_end: date,
    allocation_method: AllocationMethod = "equal_weight",
    sma_window: int = 200,
    rebalance_every: int = 21,
    friction_bps: float = 5.0,
    volatility_lookback: int = 20,
    initial_cash: float = 100_000.0,
) -> PortfolioRun:
    """Run the fixed V0.6 trend portfolio with full-frame warm-up.

    Decisions are calculated on the complete normalized history, then only
    rebalances whose next-open execution falls inside the requested period are
    replayed from a fresh initial account.  This preserves indicator warm-up
    without carrying positions or cash from another split.
    """

    bars = frames_to_portfolio_bars(frames)
    sessions = next(iter(bars.values()))
    effective_start = next(
        (bar.session for bar in sessions if bar.session >= evaluation_start),
        None,
    )
    effective_end = next(
        (bar.session for bar in reversed(sessions) if bar.session <= evaluation_end),
        None,
    )
    if (
        effective_start is None
        or effective_end is None
        or effective_start > effective_end
    ):
        raise ValueError("evaluation window has no available portfolio sessions")
    all_decisions = build_trend_decisions(
        bars,
        sma_window=sma_window,
        rebalance_every=rebalance_every,
    )
    decisions = tuple(
        decision
        for decision in all_decisions
        if effective_start <= decision.execution_session <= effective_end
    )
    result = replay_portfolio(
        bars,
        decisions,
        allocation_method=allocation_method,
        initial_cash=initial_cash,
        friction_bps=friction_bps,
        volatility_lookback=volatility_lookback,
        evaluation_start=effective_start,
        evaluation_end=effective_end,
    )
    return PortfolioRun(result=result, decisions=decisions)
