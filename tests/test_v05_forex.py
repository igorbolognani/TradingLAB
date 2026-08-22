from datetime import UTC, datetime, timedelta

import pytest

from v0_5_forex.contract import ForexBar
from v0_5_forex.replay import replay_trend_sma


def _bars(values: list[float]) -> list[ForexBar]:
    return [
        ForexBar(
            timestamp_utc=datetime(2020, 1, 1, tzinfo=UTC) + timedelta(days=i),
            open=value,
            high=value,
            low=value,
            close=value,
            volume=1,
        )
        for i, value in enumerate(values)
    ]


def test_forex_replay_uses_utc_and_next_bar_open() -> None:
    bars = _bars([100, 100, 101, 102, 103, 104])
    result = replay_trend_sma(bars, sma_window=3, friction_bps=0)
    assert result.signals[0].decision_timestamp_utc == bars[2].timestamp_utc
    assert result.signals[0].eligible_timestamp_utc == bars[3].timestamp_utc
    assert result.fills[0].timestamp_utc == bars[3].timestamp_utc
    assert result.fills[0].price == 102


def test_forex_bar_rejects_non_utc_timestamp() -> None:
    bar = _bars([100])[0]
    invalid = ForexBar(
        timestamp_utc=datetime(2020, 1, 1),
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,
    )
    with pytest.raises(ValueError, match="UTC"):
        invalid.validate()


def test_forex_bar_rejects_inconsistent_ohlc() -> None:
    invalid = ForexBar(
        timestamp_utc=datetime(2020, 1, 1, tzinfo=UTC),
        open=100,
        high=99,
        low=98,
        close=100,
        volume=1,
    )
    with pytest.raises(ValueError, match="high"):
        invalid.validate()
