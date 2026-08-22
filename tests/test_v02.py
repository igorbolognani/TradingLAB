from datetime import date, timedelta

from v0_2_lean.contract import PRIMARY_PARAMETERS
from v0_2_lean.core import Bar, replay


def _bars(start: date, closes: list[float]) -> list[Bar]:
    return [
        Bar(day, value, value, value, value, 1)
        for day, value in (
            (start + timedelta(days=i), value) for i, value in enumerate(closes)
        )
    ]


def test_v02_buy_hold_uses_next_open_and_integer_sizing() -> None:
    bars = [
        Bar(date(2006, 12, 29), 100, 100, 100, 100, 1),
        Bar(date(2007, 1, 2), 101, 101, 101, 101, 1),
        Bar(date(2007, 1, 3), 102, 102, 102, 102, 1),
    ]
    result = replay(
        bars,
        asset="SPY",
        split="development",
        strategy_id="BUY_HOLD_V1",
        friction_bps=5,
    )
    assert PRIMARY_PARAMETERS["BUY_HOLD_V1"] == {}
    assert result.fills[0].session == date(2007, 1, 2)
    assert result.fills[0].price == 101
    assert result.fills[0].quantity == 989
    assert result.fills[0].cost > 0


def test_v02_cash_is_a_zero_trade_control() -> None:
    bars = _bars(date(2006, 12, 29), [100, 101, 102, 103, 104])
    result = replay(
        bars,
        asset="SPY",
        split="development",
        strategy_id="CASH_0_V1",
        friction_bps=25,
    )
    assert result.metrics["total_return"] == 0
    assert result.metrics["modeled_costs"] == 0
    assert result.metrics["number_of_trades"] == 0


def test_v02_primary_parameters_are_frozen() -> None:
    assert PRIMARY_PARAMETERS["TREND_SMA200_V1"] == {"sma": 200}
    assert PRIMARY_PARAMETERS["MEANREV_Z20_V1"] == {
        "lookback": 20,
        "entry_z": -2.0,
        "exit_z": 0.0,
        "max_hold": 10,
    }
