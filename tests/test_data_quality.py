from datetime import date

import pandas as pd
from conftest import normalized_market_frame

from tradinglab.calendar import regular_sessions
from tradinglab.data.quality import (
    calculate_candle_summary,
    inspect_candles,
    serialize_candles,
)


def test_quality_report_accepts_complete_causal_candles() -> None:
    sessions = regular_sessions(date(2025, 1, 2), date(2025, 1, 10))
    frame = normalized_market_frame(sessions)

    report = inspect_candles(frame, expected_sessions=sessions)

    assert report["status"] == "pass"
    assert report["row_count"] == len(sessions)
    assert report["missing_session_count"] == 0
    assert report["invalid_ohlc_count"] == 0


def test_quality_report_preserves_gaps_and_structural_failures() -> None:
    sessions = regular_sessions(date(2025, 1, 2), date(2025, 1, 10))
    frame = normalized_market_frame(sessions).drop(index=sessions[2])
    duplicate = frame.iloc[[-1]].copy()
    frame.loc[frame.index[-1], "High"] = 0.0
    frame = pd.concat([frame, duplicate]).sort_index()

    report = inspect_candles(frame, expected_sessions=sessions)

    assert report["status"] == "fail"
    assert report["missing_session_count"] == 1
    assert report["duplicate_timestamp_count"] == 2
    assert report["invalid_ohlc_count"] == 1
    assert report["errors"]
    assert report["warnings"]


def test_candle_summary_and_serialization_are_json_friendly() -> None:
    sessions = regular_sessions(date(2025, 1, 2), date(2025, 4, 30))
    frame = normalized_market_frame(sessions)

    summary = calculate_candle_summary(frame)
    candles = serialize_candles(frame.tail(2))

    assert summary["latest"]["close"] is not None
    assert summary["sma_20"] is not None
    assert summary["sma_50"] is not None
    assert summary["sma_200"] is None
    assert candles[0]["event_time"].endswith("Z")
    assert candles[0]["session"] < candles[1]["session"]
