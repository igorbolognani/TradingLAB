"""Pre-registered, research-only strategy candidates for the V0.2 lab.

These candidates are deliberately outside the frozen V0.1/V0.2 primary
contract.  They are long-only, single-asset, daily and next-open compatible,
so they can be studied without changing the original strategies.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import mean, stdev

from .contract import ANNUALIZATION_SESSIONS, ASSETS, DEFAULT_FRICTION_BPS, SPLITS
from .core import Bar, load_normalized_csv


@dataclass(frozen=True)
class CandidateSignal:
    decision_session: date
    fill_session: date
    action: str
    reason: str
    indicator: float | None


@dataclass(frozen=True)
class CandidateResult:
    asset: str
    split: str
    strategy_id: str
    signals: tuple[CandidateSignal, ...]
    fills: int
    metrics: dict[str, float | int | None]


CANDIDATE_IDS = (
    "TSMOM_12M_RESEARCH_V1",
    "TREND_BLEND_3_6_12_RESEARCH_V1",
    "TREND_GATED_MEANREV_RESEARCH_V1",
)


def _sma(closes: list[float], index: int, window: int) -> float | None:
    if index + 1 < window:
        return None
    return mean(closes[index + 1 - window : index + 1])


def _zscore(closes: list[float], index: int, window: int) -> float | None:
    if index + 1 < window:
        return None
    sample = closes[index + 1 - window : index + 1]
    average = mean(sample)
    deviation = math.sqrt(mean((value - average) ** 2 for value in sample))
    return None if deviation == 0 else (closes[index] - average) / deviation


def _momentum(closes: list[float], index: int, window: int) -> float | None:
    if index < window:
        return None
    return closes[index] / closes[index - window] - 1


def _decision(
    strategy_id: str,
    closes: list[float],
    index: int,
    invested: bool,
    held_sessions: int,
) -> tuple[str | None, str | None, float | None]:
    if strategy_id == "TSMOM_12M_RESEARCH_V1":
        value = _momentum(closes, index, 252)
        if value is None:
            return None, None, None
        if not invested and value > 0:
            return "enter", "positive_12m_momentum", value
        if invested and value <= 0:
            return "exit", "nonpositive_12m_momentum", value
        return None, None, value

    if strategy_id == "TREND_BLEND_3_6_12_RESEARCH_V1":
        values = [_momentum(closes, index, window) for window in (63, 126, 252)]
        if any(value is None for value in values):
            return None, None, None
        score = sum(value is not None and value > 0 for value in values) / 3
        if not invested and score >= 2 / 3:
            return "enter", "two_of_three_trends_positive", score
        if invested and score <= 1 / 3:
            return "exit", "two_of_three_trends_nonpositive", score
        return None, None, score

    if strategy_id == "TREND_GATED_MEANREV_RESEARCH_V1":
        sma = _sma(closes, index, 200)
        zscore = _zscore(closes, index, 20)
        if sma is None or zscore is None:
            return None, None, None
        if not invested and closes[index] > sma and zscore <= -2:
            return "enter", "uptrend_meanrev_dip", zscore
        if invested and closes[index] <= sma:
            return "exit", "trend_gate_lost", sma
        if invested and zscore >= 0:
            return "exit", "meanrev_normalized", zscore
        if invested and held_sessions >= 10:
            return "exit", "max_hold_exit", zscore
        return None, None, zscore

    raise ValueError(f"unknown research strategy: {strategy_id}")


def replay_candidate(
    bars: list[Bar],
    *,
    asset: str,
    split: str,
    strategy_id: str,
    friction_bps: int = DEFAULT_FRICTION_BPS,
) -> CandidateResult:
    """Replay one candidate with the frozen V0.2 accounting convention."""

    if strategy_id not in CANDIDATE_IDS:
        raise ValueError(f"unknown research strategy: {strategy_id}")
    start, end = SPLITS[split]
    indices = [i for i, bar in enumerate(bars) if start <= bar.session <= end]
    if not indices:
        raise ValueError(f"no bars in split {split}")
    closes = [bar.close for bar in bars]
    cash = 100_000.0
    quantity = 0
    held_sessions = 0
    costs = 0.0
    pending: tuple[str, str, float | None, date] | None = None
    signals: list[CandidateSignal] = []
    equity: list[float] = []
    invested_flags: list[bool] = []
    fill_count = 0
    rate = friction_bps / 10_000

    for index, bar in enumerate(bars):
        if index > indices[-1]:
            break
        if pending is not None and index in indices:
            pending_action, _pending_reason, _indicator, _fill_session = pending
            if pending_action == "enter" and quantity == 0:
                buy_quantity = math.floor(cash / (bar.open * (1 + rate)))
                if buy_quantity > 0:
                    cost = buy_quantity * bar.open * rate
                    cash -= buy_quantity * bar.open + cost
                    quantity = buy_quantity
                    costs += cost
                    fill_count += 1
                    held_sessions = 1
            elif pending_action == "exit" and quantity > 0:
                cost = quantity * bar.open * rate
                cash += quantity * bar.open - cost
                quantity = 0
                costs += cost
                fill_count += 1
                held_sessions = 0
            pending = None

        if index in indices:
            equity.append(cash + quantity * bar.close)
            invested_flags.append(quantity > 0)
            if quantity > 0:
                held_sessions += 1

        if index >= indices[0] and index < indices[-1] and pending is None:
            next_session = bars[index + 1].session
            decision_action, decision_reason, indicator = _decision(
                strategy_id, closes, index, quantity > 0, held_sessions
            )
            if decision_action is not None and decision_reason is not None:
                pending = (decision_action, decision_reason, indicator, next_session)
                signals.append(
                    CandidateSignal(
                        bar.session,
                        next_session,
                        decision_action,
                        decision_reason,
                        indicator,
                    )
                )

    returns = [equity[0] / 100_000 - 1]
    returns.extend(equity[i] / equity[i - 1] - 1 for i in range(1, len(equity)))
    total_return = equity[-1] / 100_000 - 1
    cagr = (equity[-1] / 100_000) ** (ANNUALIZATION_SESSIONS / len(equity)) - 1
    volatility = (
        stdev(returns) * math.sqrt(ANNUALIZATION_SESSIONS) if len(returns) > 1 else None
    )
    sharpe = (
        mean(returns) / stdev(returns) * math.sqrt(ANNUALIZATION_SESSIONS)
        if len(returns) > 1 and stdev(returns) != 0
        else None
    )
    running_max = equity[0]
    drawdowns: list[float] = []
    for value in equity:
        running_max = max(running_max, value)
        drawdowns.append(value / running_max - 1)
    return CandidateResult(
        asset=asset,
        split=split,
        strategy_id=strategy_id,
        signals=tuple(signals),
        fills=fill_count,
        metrics={
            "total_return": total_return,
            "CAGR": cagr,
            "annualized_volatility": volatility,
            "Sharpe": sharpe,
            "max_drawdown": min(drawdowns),
            "number_of_fills": fill_count,
            "modeled_costs": costs,
            "exposure": mean(invested_flags),
        },
    )


def run_candidate_battery(snapshot_root: Path, output_csv: Path) -> int:
    """Run fixed candidates for all assets/splits without touching V0.1."""

    rows: list[dict[str, str]] = []
    for asset in ASSETS:
        bars = load_normalized_csv(snapshot_root / asset / "normalized.csv")
        for split in SPLITS:
            for strategy_id in CANDIDATE_IDS:
                result = replay_candidate(
                    bars,
                    asset=asset,
                    split=split,
                    strategy_id=strategy_id,
                )
                rows.append(
                    {
                        "asset": asset,
                        "split": split,
                        "strategy_id": strategy_id,
                        **{
                            key: "" if value is None else str(value)
                            for key, value in result.metrics.items()
                        },
                    }
                )
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
