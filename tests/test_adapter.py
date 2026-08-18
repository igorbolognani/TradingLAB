import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from conftest import normalized_market_frame

from tradinglab.adapter import AdapterResult, BacktestingPyAdapter, engine_configuration
from tradinglab.calendar import regular_sessions
from tradinglab.constants import INITIAL_CASH, TemporalSplit
from tradinglab.specs import load_spec


def run(
    spec_dir: Path,
    strategy_id: str,
    data: pd.DataFrame,
    parameters: dict[str, float | int],
    start: date,
    end: date,
    friction: int = 5,
) -> AdapterResult:
    return BacktestingPyAdapter().run(
        data=data,
        spec=load_spec(spec_dir / f"{strategy_id}.yaml"),
        parameters=parameters,
        split=TemporalSplit("synthetic", "Synthetic", start, end),
        friction_bps=friction,
    )


def test_cash_control_has_no_trades_costs_or_interest(spec_dir: Path) -> None:
    sessions = regular_sessions(date(2025, 1, 2), date(2025, 1, 10))
    result = run(
        spec_dir,
        "CASH_0_V1",
        normalized_market_frame(sessions),
        {},
        date(2025, 1, 2),
        date(2025, 1, 10),
    )
    assert result.trades.empty
    assert (result.equity_curve["net_equity"] == INITIAL_CASH).all()
    assert (result.equity_curve["cumulative_modeled_costs"] == 0).all()
    assert result.terminal_position_open is False


def test_buy_hold_integer_sizing_friction_and_terminal_mark(spec_dir: Path) -> None:
    sessions = regular_sessions(date(2025, 1, 2), date(2025, 1, 10))
    closes = [100 + offset for offset in range(len(sessions))]
    data = normalized_market_frame(
        sessions,
        opens=[100] * len(sessions),
        closes=closes,
    )
    result = run(spec_dir, "BUY_HOLD_V1", data, {}, date(2025, 1, 2), date(2025, 1, 10))
    expected_quantity = math.floor(INITIAL_CASH / (100 * 1.0005))
    entry = result.trades.iloc[0]
    assert int(entry["quantity"]) == expected_quantity
    assert entry["modeled_friction"] == expected_quantity * 100 * 0.0005
    assert entry["side"] == "buy"
    assert entry["terminal_status"] == "open"
    assert len(result.trades) == 1
    assert result.terminal_position_open is True
    assert result.equity_curve.iloc[-1]["normalized_close"] == closes[-1]


def test_close_signal_fills_next_xnys_open_across_weekend_and_holiday(
    spec_dir: Path,
) -> None:
    sessions = pd.DatetimeIndex(
        [
            pd.Timestamp(value, tz="America/New_York")
            for value in (
                "2025-01-15",
                "2025-01-16",
                "2025-01-17",
                "2025-01-21",
                "2025-01-22",
                "2025-01-23",
            )
        ],
        name="Session",
    )
    data = normalized_market_frame(
        sessions,
        closes=[10, 10, 12, 12, 8, 8],
        opens=[10, 10, 11, 13, 12, 7],
    )
    result = run(
        spec_dir,
        "TREND_SMA200_V1",
        data,
        {"sma": 2},
        date(2025, 1, 17),
        date(2025, 1, 23),
    )
    buy = result.trades[result.trades["side"] == "buy"].iloc[0]
    sell = result.trades[result.trades["side"] == "sell"].iloc[0]
    assert buy["signal_session"] == "2025-01-17"
    assert buy["fill_session"] == "2025-01-21"
    assert buy["normalized_fill_price"] == 13
    assert sell["signal_session"] == "2025-01-21"
    assert sell["fill_session"] == "2025-01-22"
    assert sell["normalized_fill_price"] == 12
    assert not (result.trades["signal_session"] == result.trades["fill_session"]).any()


def test_entry_and_exit_friction_are_once_each_and_reconcile(spec_dir: Path) -> None:
    sessions = regular_sessions(date(2025, 1, 2), date(2025, 1, 15))
    closes = [10, 10, 12, 12, 8, 8, 8, 8, 8]
    opens = [10, 10, 10, 10, 10, 10, 10, 10, 10]
    data = normalized_market_frame(sessions, closes=closes, opens=opens)
    result = run(
        spec_dir,
        "TREND_SMA200_V1",
        data,
        {"sma": 2},
        sessions[2].date(),
        sessions[-1].date(),
    )
    assert list(result.trades["side"]) == ["buy", "sell"]
    expected_cost = float(
        (
            result.trades["quantity"] * result.trades["normalized_fill_price"] * 0.0005
        ).sum()
    )
    assert result.trades["modeled_friction"].sum() == expected_cost
    np.testing.assert_allclose(
        result.equity_curve["gross_equity"]
        - result.equity_curve["cumulative_modeled_costs"],
        result.equity_curve["net_equity"],
    )
    assert result.trades["lifecycle_id"].nunique() == 1


def test_mean_reversion_counts_entry_fill_as_held_session_one(
    spec_dir: Path,
) -> None:
    sessions = regular_sessions(date(2025, 2, 3), date(2025, 2, 13))
    closes = [10, 10, 8, 8, 8, 8, 8, 8, 8]
    data = normalized_market_frame(sessions, closes=closes, opens=closes)
    result = run(
        spec_dir,
        "MEANREV_Z20_V1",
        data,
        {"lookback": 2, "entry_z": -0.5, "exit_z": 0.0, "max_hold": 3},
        sessions[1].date(),
        sessions[-1].date(),
    )
    entry = result.trades[result.trades["side"] == "buy"].iloc[0]
    exit_ = result.trades[result.trades["side"] == "sell"].iloc[0]
    assert entry["fill_session"] == sessions[3].date().isoformat()
    assert entry["held_session_count"] == 3
    assert exit_["signal_session"] == sessions[5].date().isoformat()
    assert exit_["fill_session"] == sessions[6].date().isoformat()
    assert exit_["exit_reason"] == "max_hold_exit"
    assert exit_["held_session_count"] == 3
    assert len(result.trades[result.trades["side"] == "buy"]) == 1
    assert result.signals.iloc[0]["decision_session"] == sessions[2].date().isoformat()


def test_insufficient_cash_entry_is_skipped_and_recorded(spec_dir: Path) -> None:
    sessions = regular_sessions(date(2025, 1, 2), date(2025, 1, 3))
    data = normalized_market_frame(
        sessions, opens=[200_000, 200_000], closes=[200_000, 200_000]
    )
    result = run(
        spec_dir, "BUY_HOLD_V1", data, {}, sessions[0].date(), sessions[-1].date()
    )
    assert result.trades.empty
    assert result.signals.iloc[0]["fill_status"] == "skipped_insufficient_cash"
    assert result.equity_curve.iloc[-1]["cash"] == INITIAL_CASH


def test_engine_options_are_all_explicit_and_safe() -> None:
    configuration = engine_configuration(5)
    assert configuration == {
        "cash": 100_000.0,
        "spread": 0.0,
        "commission": 0.0005,
        "margin": 1.0,
        "trade_on_close": False,
        "hedging": False,
        "exclusive_orders": True,
        "finalize_trades": False,
        "integer_size": True,
        "terminal_handling": "mark_to_final_normalized_close_without_forced_exit",
    }


def test_final_close_decision_is_preserved_without_a_future_session(
    spec_dir: Path,
) -> None:
    sessions = regular_sessions(date(2025, 3, 3), date(2025, 3, 5))
    data = normalized_market_frame(sessions, closes=[10, 10, 12], opens=[10, 10, 10])
    result = run(
        spec_dir,
        "TREND_SMA200_V1",
        data,
        {"sma": 2},
        sessions[1].date(),
        sessions[-1].date(),
    )
    final_signal = result.signals.iloc[-1]
    assert final_signal["decision_session"] == sessions[-1].date().isoformat()
    assert final_signal["action"] == "enter"
    assert final_signal["order_eligibility_session"] is None
    assert final_signal["fill_status"] == "no_next_session"


def test_adapter_signal_decisions_are_prefix_invariant_for_stateful_strategies(
    spec_dir: Path,
) -> None:
    sessions = regular_sessions(date(2025, 1, 2), date(2025, 3, 14))
    pattern = [100, 101, 103, 96, 92, 99, 104, 105, 94, 89]
    closes = [float(pattern[index % len(pattern)]) for index in range(len(sessions))]
    data = normalized_market_frame(sessions, closes=closes, opens=closes)
    cases: tuple[tuple[str, dict[str, float | int]], ...] = (
        ("TREND_SMA200_V1", {"sma": 3}),
        (
            "MEANREV_Z20_V1",
            {"lookback": 3, "entry_z": -0.8, "exit_z": 0.0, "max_hold": 4},
        ),
    )
    core = ["decision_session", "action", "reason", "indicator_value"]
    for strategy_id, parameters in cases:
        full = run(
            spec_dir,
            strategy_id,
            data,
            parameters,
            sessions[3].date(),
            sessions[-1].date(),
        )
        assert not full.signals.empty
        for cut in (10, 20, 30, 40):
            prefix = run(
                spec_dir,
                strategy_id,
                data.iloc[: cut + 1],
                parameters,
                sessions[3].date(),
                sessions[cut].date(),
            )
            cutoff = sessions[cut].date().isoformat()
            expected = full.signals[
                full.signals["decision_session"].notna()
                & (full.signals["decision_session"] <= cutoff)
            ][core].reset_index(drop=True)
            actual = prefix.signals[core].reset_index(drop=True)
            pd.testing.assert_frame_equal(actual, expected)
