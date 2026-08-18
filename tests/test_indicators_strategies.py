import numpy as np
import pandas as pd

from tradinglab.indicators import population_zscore, simple_moving_average
from tradinglab.strategies import DecisionMachine


def test_sma_known_values_and_explicit_warmup() -> None:
    close = pd.Series([1.0, 2.0, 3.0, 4.0])
    result = simple_moving_average(close, 3)
    assert result.iloc[:2].isna().all()
    np.testing.assert_allclose(result.iloc[2:], [2.0, 3.0])


def test_population_zscore_ddof_zero_and_zero_volatility() -> None:
    close = pd.Series([1.0, 2.0, 3.0])
    result = population_zscore(close, 3)
    expected = (3.0 - 2.0) / np.std([1.0, 2.0, 3.0], ddof=0)
    assert result.iloc[2] == expected
    assert population_zscore(pd.Series([2.0, 2.0, 2.0]), 3).isna().all()


def test_trend_exact_targets_equality_and_no_duplicate_transition() -> None:
    machine = DecisionMachine("TREND_SMA200_V1", {"sma": 200})
    enter = machine.after_close(
        close=101, indicator=100, in_position=False, held_sessions=0
    )
    assert enter is not None and enter.action == "enter"
    assert (
        machine.after_close(close=101, indicator=100, in_position=True, held_sessions=1)
        is None
    )
    exit_ = machine.after_close(
        close=100, indicator=100, in_position=True, held_sessions=2
    )
    assert exit_ is not None and exit_.action == "exit"
    assert (
        machine.after_close(close=99, indicator=100, in_position=False, held_sessions=0)
        is None
    )


def test_mean_reversion_entry_z_exit_max_hold_and_zero_volatility() -> None:
    parameters = {"lookback": 20, "entry_z": -2.0, "exit_z": 0.0, "max_hold": 10}
    machine = DecisionMachine("MEANREV_Z20_V1", parameters)
    enter = machine.after_close(
        close=90, indicator=-2.0, in_position=False, held_sessions=0
    )
    assert enter is not None and enter.reason == "zscore_entry"
    assert (
        machine.after_close(close=89, indicator=-3.0, in_position=True, held_sessions=5)
        is None
    )
    z_exit = machine.after_close(
        close=100, indicator=0.0, in_position=True, held_sessions=6
    )
    assert z_exit is not None and z_exit.reason == "zscore_exit"
    hold_exit = machine.after_close(
        close=80, indicator=float("nan"), in_position=True, held_sessions=10
    )
    assert hold_exit is not None and hold_exit.reason == "max_hold_exit"
    assert (
        machine.after_close(
            close=80, indicator=float("nan"), in_position=False, held_sessions=0
        )
        is None
    )


def _trace(
    close: pd.Series, strategy_id: str, parameters: dict[str, float | int]
) -> list[tuple[int, str, str]]:
    indicator = (
        simple_moving_average(close, int(parameters["sma"]))
        if strategy_id == "TREND_SMA200_V1"
        else population_zscore(close, int(parameters["lookback"]))
    )
    machine = DecisionMachine(strategy_id, parameters)
    in_position = False
    held = 0
    result: list[tuple[int, str, str]] = []
    for offset in range(len(close)):
        if in_position:
            held += 1
        decision = machine.after_close(
            close=float(close.iloc[offset]),
            indicator=float(indicator.iloc[offset]),
            in_position=in_position,
            held_sessions=held,
        )
        if decision is not None:
            result.append((offset, decision.action, decision.reason))
            in_position = decision.action == "enter"
            held = 0
    return result


def test_prefix_invariance_at_multiple_cut_points_for_both_strategies() -> None:
    close = pd.Series([100 + np.sin(i / 3) * 10 + i * 0.05 for i in range(120)])
    cases: list[tuple[str, dict[str, float | int]]] = [
        ("TREND_SMA200_V1", {"sma": 15}),
        (
            "MEANREV_Z20_V1",
            {"lookback": 10, "entry_z": -1.2, "exit_z": 0.0, "max_hold": 6},
        ),
    ]
    for strategy_id, parameters in cases:
        full = _trace(close, strategy_id, parameters)
        for cut in (25, 50, 80, 100):
            prefix = _trace(close.iloc[:cut], strategy_id, parameters)
            assert prefix == [item for item in full if item[0] < cut]
