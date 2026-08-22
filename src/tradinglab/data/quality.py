"""Quality checks and derived values for auditable OHLCV candles.

The checks in this module are deliberately provider-neutral.  A provider may
send different field names or timestamps, but after normalization the rest of
TradingLAB receives one explicit candle contract.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import numpy as np
import pandas as pd

CANDLE_COLUMNS: tuple[str, ...] = ("Open", "High", "Low", "Close", "Volume")


def _iso(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC").isoformat()


def _json_number(value: Any) -> float | int | None:
    if value is None or pd.isna(value):
        return None
    numeric = float(value)
    if not np.isfinite(numeric):
        return None
    return numeric


def inspect_candles(
    frame: pd.DataFrame,
    *,
    expected_sessions: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    """Return a serializable quality report without mutating ``frame``.

    Structural violations are failures.  Missing exchange sessions are
    warnings because a provider can legitimately omit a session only when the
    caller has chosen a narrower session or the provider has a known gap; the
    report keeps the gap visible so that a caller can decide whether to stop.
    """

    errors: list[str] = []
    warnings: list[str] = []
    missing_columns = [column for column in CANDLE_COLUMNS if column not in frame]

    if not isinstance(frame.index, pd.DatetimeIndex):
        errors.append("index is not a DatetimeIndex")
        index = pd.DatetimeIndex([], tz="UTC")
    else:
        index = frame.index

    duplicate_count = int(index.duplicated(keep=False).sum())
    out_of_order_count = int((index[1:] < index[:-1]).sum()) if len(index) > 1 else 0
    if duplicate_count:
        errors.append("duplicate candle timestamps")
    if out_of_order_count:
        errors.append("candle timestamps are not chronological")
    if missing_columns:
        errors.append(f"missing candle columns: {missing_columns}")

    missing_value_count = 0
    invalid_ohlc_count = 0
    negative_volume_count = 0
    nonfinite_count = 0
    if not missing_columns:
        values = frame.loc[:, list(CANDLE_COLUMNS)].apply(
            pd.to_numeric, errors="coerce"
        )
        missing_value_count = int(values.isna().sum().sum())
        nonfinite_count = int((~np.isfinite(values.to_numpy(dtype=float))).sum())
        prices = values.loc[:, ["Open", "High", "Low", "Close"]]
        invalid_ohlc_count = int(
            (
                (prices["High"] < prices[["Open", "Close", "Low"]].max(axis=1))
                | (prices["Low"] > prices[["Open", "Close", "High"]].min(axis=1))
                | (prices[["Open", "High", "Low", "Close"]] <= 0).any(axis=1)
            ).sum()
        )
        negative_volume_count = int((values["Volume"] < 0).sum())
        if missing_value_count:
            errors.append("required candle values are missing or nonnumeric")
        if nonfinite_count:
            errors.append("required candle values are not finite")
        if invalid_ohlc_count:
            errors.append("OHLC relationship or positive-price invariant failed")
        if negative_volume_count:
            errors.append("negative volume found")

    missing_sessions: list[str] = []
    unexpected_sessions: list[str] = []
    if expected_sessions is not None and isinstance(frame.index, pd.DatetimeIndex):
        expected = expected_sessions
        if expected.tz is None and index.tz is not None:
            expected = expected.tz_localize(index.tz)
        elif expected.tz is not None and index.tz is not None:
            expected = expected.tz_convert(index.tz)
        missing = expected.difference(index)
        unexpected = index.difference(expected)
        missing_sessions = [value.date().isoformat() for value in missing]
        unexpected_sessions = [value.date().isoformat() for value in unexpected]
        if missing_sessions:
            warnings.append(f"{len(missing_sessions)} expected sessions are absent")
        if unexpected_sessions:
            warnings.append(f"{len(unexpected_sessions)} sessions are unexpected")

    status = "fail" if errors else "warning" if warnings else "pass"
    return {
        "status": status,
        "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "row_count": len(frame),
        "first_event_time": _iso(index.min()) if len(index) else None,
        "last_event_time": _iso(index.max()) if len(index) else None,
        "duplicate_timestamp_count": duplicate_count,
        "out_of_order_count": out_of_order_count,
        "missing_value_count": missing_value_count,
        "nonfinite_value_count": nonfinite_count,
        "invalid_ohlc_count": invalid_ohlc_count,
        "negative_volume_count": negative_volume_count,
        "missing_session_count": len(missing_sessions),
        "missing_sessions": missing_sessions[:25],
        "unexpected_session_count": len(unexpected_sessions),
        "unexpected_sessions": unexpected_sessions[:25],
        "errors": errors,
        "warnings": warnings,
    }


def calculate_candle_summary(frame: pd.DataFrame) -> dict[str, Any]:
    """Calculate transparent indicators from the normalized candle frame."""

    if not len(frame):
        return {
            "latest": None,
            "change": None,
            "change_pct": None,
            "session_range_pct": None,
            "atr_14": None,
            "sma_20": None,
            "sma_50": None,
            "sma_200": None,
            "volume_vs_20_session_median": None,
        }

    values = frame.loc[:, list(CANDLE_COLUMNS)].apply(pd.to_numeric, errors="coerce")
    close = values["Close"]
    high = values["High"]
    low = values["Low"]
    previous_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    latest = values.iloc[-1]
    latest_close = float(latest["Close"])
    previous = _json_number(previous_close.iloc[-1])
    if previous is None or previous == 0:
        change = None
        change_pct = None
    else:
        previous_value = float(previous)
        change = latest_close - previous_value
        change_pct = change / previous_value
    range_pct = (
        (float(latest["High"]) - float(latest["Low"])) / latest_close
        if latest_close
        else None
    )
    volume_median = values["Volume"].rolling(20, min_periods=1).median().iloc[-1]
    return {
        "latest": {
            "open": _json_number(latest["Open"]),
            "high": _json_number(latest["High"]),
            "low": _json_number(latest["Low"]),
            "close": _json_number(latest["Close"]),
            "volume": _json_number(latest["Volume"]),
        },
        "change": _json_number(change),
        "change_pct": _json_number(change_pct),
        "session_range_pct": _json_number(range_pct),
        "atr_14": _json_number(true_range.rolling(14, min_periods=1).mean().iloc[-1]),
        "sma_20": _json_number(close.rolling(20, min_periods=20).mean().iloc[-1]),
        "sma_50": _json_number(close.rolling(50, min_periods=50).mean().iloc[-1]),
        "sma_200": _json_number(close.rolling(200, min_periods=200).mean().iloc[-1]),
        "volume_vs_20_session_median": _json_number(
            float(latest["Volume"]) / float(volume_median)
            if volume_median not in (None, 0)
            else None
        ),
    }


def serialize_candles(
    frame: pd.DataFrame,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Serialize normalized candles and causal indicator values.

    Indicators are calculated on the complete frame before the optional tail
    is selected. This prevents a chart request for the last 240 rows from
    silently changing the warm-up semantics of SMA200.
    """

    values = frame.loc[:, list(CANDLE_COLUMNS)].apply(pd.to_numeric, errors="coerce")
    close = values["Close"]
    high = values["High"]
    low = values["Low"]
    previous_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    indicator_frame = pd.DataFrame(
        {
            "sma_20": close.rolling(20, min_periods=20).mean(),
            "sma_50": close.rolling(50, min_periods=50).mean(),
            "sma_200": close.rolling(200, min_periods=200).mean(),
            "atr_14": true_range.rolling(14, min_periods=1).mean(),
        },
        index=frame.index,
    )
    source = frame.tail(limit) if limit is not None else frame
    candles: list[dict[str, Any]] = []
    source_offset = len(frame) - len(source)
    for position, (timestamp, row) in enumerate(source.iterrows()):
        event_time = pd.Timestamp(cast(Any, timestamp))
        if event_time.tzinfo is None:
            event_time = event_time.tz_localize("UTC")
        event_time = event_time.tz_convert("UTC")
        indicator_row = indicator_frame.iloc[source_offset + position]
        candles.append(
            {
                "event_time": event_time.isoformat().replace("+00:00", "Z"),
                "session": event_time.date().isoformat(),
                "open": _json_number(row["Open"]),
                "high": _json_number(row["High"]),
                "low": _json_number(row["Low"]),
                "close": _json_number(row["Close"]),
                "volume": _json_number(row["Volume"]),
                "sma_20": _json_number(indicator_row["sma_20"]),
                "sma_50": _json_number(indicator_row["sma_50"]),
                "sma_200": _json_number(indicator_row["sma_200"]),
                "atr_14": _json_number(indicator_row["atr_14"]),
            }
        )
    return candles
