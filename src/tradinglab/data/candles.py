"""Provider-neutral canonical candle files and freshness diagnostics.

This module deliberately has no provider or broker dependency. It accepts a
small, documented CSV contract so a licensed export, a Databento/Polygon
adapter, or a user-owned feed can supply candles without changing the research
engine. The file path is explicit and the data is never downloaded here.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from itertools import pairwise
from pathlib import Path
from statistics import fmean, median
from typing import Any

CANONICAL_CANDLE_SCHEMA = "tradinglab.candle.v1"
REQUIRED_CANDLE_ALIASES = ("open", "high", "low", "close", "volume")


def _field(row: Mapping[str, str], *aliases: str) -> str | None:
    for alias in aliases:
        value = row.get(alias.lower())
        if value is not None and value.strip() != "":
            return value.strip()
    return None


def _parse_timestamp(value: str | None, field_name: str) -> datetime:
    if value is None:
        raise ValueError(f"{field_name} is required")
    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        raise ValueError(f"{field_name} must include an explicit UTC timestamp")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} is not a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(None):
        raise ValueError(f"{field_name} must include an explicit UTC offset")
    return parsed.astimezone(UTC)


def _parse_float(value: str | None, field_name: str) -> float:
    if value is None:
        raise ValueError(f"{field_name} is required")
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} is not numeric") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{field_name} must be finite")
    return parsed


def _optional_float(value: str | None, field_name: str) -> float | None:
    return None if value is None else _parse_float(value, field_name)


def _optional_int(value: str | None, field_name: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} is not an integer") from exc


def _optional_bool(value: str | None, field_name: str) -> bool | None:
    if value is None:
        return None
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"{field_name} must be true/false when supplied")


@dataclass(frozen=True, slots=True)
class CanonicalCandle:
    """One provider-neutral candle with explicit clocks and provenance."""

    instrument_id: str
    symbol: str
    venue: str
    feed: str
    interval: str
    bar_start_utc: datetime
    bar_end_utc: datetime
    session_date: date
    event_time_utc: datetime
    receive_time_utc: datetime | None
    is_complete: bool | None
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float | None
    trade_count: int | None
    price_basis: str
    provider: str
    provider_version: str
    sequence: int | None
    quality_flags: tuple[str, ...]

    def validate(self) -> None:
        if not self.instrument_id or not self.symbol or not self.interval:
            raise ValueError("instrument_id, symbol, and interval are required")
        timestamps = (self.bar_start_utc, self.bar_end_utc, self.event_time_utc)
        if any(timestamp.tzinfo is None for timestamp in timestamps):
            raise ValueError("candle timestamps must be timezone-aware")
        if any(
            timestamp.utcoffset() != UTC.utcoffset(None) for timestamp in timestamps
        ):
            raise ValueError("candle timestamps must be UTC")
        prices = (self.open, self.high, self.low, self.close)
        if any(not math.isfinite(price) or price <= 0 for price in prices):
            raise ValueError("OHLC values must be finite and positive")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be at least open, close, and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be at most open, close, and high")
        if not math.isfinite(self.volume) or self.volume < 0:
            raise ValueError("volume must be finite and non-negative")
        if self.receive_time_utc is not None:
            if self.receive_time_utc.tzinfo is None:
                raise ValueError("receive_time_utc must be timezone-aware")
            if self.receive_time_utc.utcoffset() != UTC.utcoffset(None):
                raise ValueError("receive_time_utc must be UTC")
            if self.receive_time_utc < self.event_time_utc:
                raise ValueError("receive_time_utc cannot precede event_time_utc")


def _row_to_candle(
    row: Mapping[str, str],
    *,
    row_number: int,
    default_symbol: str | None,
    default_provider: str,
    default_provider_version: str,
) -> CanonicalCandle:
    timestamp = _field(
        row,
        "bar_start_utc",
        "timestamp_utc",
        "event_time_utc",
        "timestamp",
        "datetime",
        "date",
    )
    event_time = _parse_timestamp(
        _field(row, "event_time_utc") or timestamp,
        "event_time_utc",
    )
    bar_start = _parse_timestamp(timestamp, "bar_start_utc")
    bar_end = _parse_timestamp(
        _field(row, "bar_end_utc") or timestamp,
        "bar_end_utc",
    )
    symbol = _field(row, "symbol", "ticker") or default_symbol
    if symbol is None:
        raise ValueError(f"row {row_number}: symbol is required")
    receive_value = _field(row, "receive_time_utc")
    candle = CanonicalCandle(
        instrument_id=_field(row, "instrument_id") or symbol,
        symbol=symbol,
        venue=_field(row, "venue") or "unknown",
        feed=_field(row, "feed") or "unknown",
        interval=_field(row, "interval", "timeframe") or "unknown",
        bar_start_utc=bar_start,
        bar_end_utc=bar_end,
        session_date=date.fromisoformat(
            _field(row, "session_date") or event_time.date().isoformat()
        ),
        event_time_utc=event_time,
        receive_time_utc=(
            _parse_timestamp(receive_value, "receive_time_utc")
            if receive_value is not None
            else None
        ),
        is_complete=_optional_bool(_field(row, "is_complete"), "is_complete"),
        open=_parse_float(_field(row, "open"), "open"),
        high=_parse_float(_field(row, "high"), "high"),
        low=_parse_float(_field(row, "low"), "low"),
        close=_parse_float(_field(row, "close"), "close"),
        volume=_parse_float(_field(row, "volume"), "volume"),
        vwap=_optional_float(_field(row, "vwap"), "vwap"),
        trade_count=_optional_int(_field(row, "trade_count", "count"), "trade_count"),
        price_basis=_field(row, "price_basis") or "unknown",
        provider=_field(row, "provider") or default_provider,
        provider_version=_field(row, "provider_version") or default_provider_version,
        sequence=_optional_int(_field(row, "sequence"), "sequence"),
        quality_flags=tuple(
            flag for flag in (_field(row, "quality_flags") or "").split("|") if flag
        ),
    )
    try:
        candle.validate()
    except ValueError as exc:
        raise ValueError(f"row {row_number}: {exc}") from exc
    return candle


def load_candle_csv(
    path: Path,
    *,
    symbol: str | None = None,
    provider: str = "user-supplied-file",
    provider_version: str = CANONICAL_CANDLE_SCHEMA,
) -> tuple[CanonicalCandle, ...]:
    """Load a user-owned or licensed CSV without network access.

    The minimum accepted columns are a UTC timestamp, symbol (unless supplied
    as an argument), and OHLCV. Remaining canonical fields become explicit
    ``unknown``/``None`` values rather than being guessed.
    """

    if not path.is_file():
        raise ValueError(f"candle file does not exist: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = {str(field).strip().lower() for field in (reader.fieldnames or [])}
        if not fields:
            raise ValueError("candle file has no header")
        missing = [field for field in REQUIRED_CANDLE_ALIASES if field not in fields]
        timestamp_aliases = {
            "bar_start_utc",
            "timestamp_utc",
            "event_time_utc",
            "timestamp",
            "datetime",
            "date",
        }
        if missing or not fields.intersection(timestamp_aliases):
            required = [*missing, "timestamp_utc"] if missing else ["timestamp_utc"]
            raise ValueError(f"candle file is missing required fields: {required}")
        rows: list[CanonicalCandle] = []
        for row_number, raw_row in enumerate(reader, start=2):
            normalized = {
                str(key).strip().lower(): str(value or "")
                for key, value in raw_row.items()
                if key is not None
            }
            candle = _row_to_candle(
                normalized,
                row_number=row_number,
                default_symbol=symbol,
                default_provider=provider,
                default_provider_version=provider_version,
            )
            if symbol is None or candle.symbol == symbol:
                rows.append(candle)
    if not rows:
        raise ValueError("candle file contains no rows for the requested symbol")
    return tuple(rows)


def inspect_candles(
    rows: Sequence[CanonicalCandle], *, now: datetime | None = None
) -> dict[str, Any]:
    """Return quality, completeness, and clock diagnostics for a feed."""

    if not rows:
        raise ValueError("candle inspection requires at least one row")
    timestamps = [row.event_time_utc for row in rows]
    duplicate_count = len(timestamps) - len(set(timestamps))
    out_of_order_count = sum(
        current < previous for previous, current in pairwise(timestamps)
    )
    incomplete_count = sum(row.is_complete is False for row in rows)
    unknown_complete_count = sum(row.is_complete is None for row in rows)
    receive_times = [row.receive_time_utc for row in rows if row.receive_time_utc]
    latencies_ms = [
        (receive - row.event_time_utc).total_seconds() * 1000
        for row in rows
        if (receive := row.receive_time_utc) is not None
    ]
    errors: list[str] = []
    warnings: list[str] = []
    if duplicate_count:
        errors.append(f"{duplicate_count} duplicate event timestamps")
    if out_of_order_count:
        errors.append(f"{out_of_order_count} out-of-order event timestamps")
    if incomplete_count:
        warnings.append(f"{incomplete_count} candles are not complete")
    if unknown_complete_count:
        warnings.append(f"{unknown_complete_count} candles have unknown completeness")
    if not receive_times:
        warnings.append("receive_time_utc is unavailable; latency cannot be measured")
    if any(latency < 0 for latency in latencies_ms):
        errors.append("negative event-to-receive latency")
    status = "fail" if errors else "warning" if warnings else "pass"
    observed_at = (now or datetime.now(UTC)).astimezone(UTC)
    latest_event = max(timestamps)
    latest_receive = max(receive_times) if receive_times else None
    return {
        "schema": CANONICAL_CANDLE_SCHEMA,
        "status": status,
        "row_count": len(rows),
        "duplicate_timestamp_count": duplicate_count,
        "out_of_order_count": out_of_order_count,
        "incomplete_count": incomplete_count,
        "unknown_completeness_count": unknown_complete_count,
        "errors": errors,
        "warnings": warnings,
        "first_event_time": min(timestamps).isoformat().replace("+00:00", "Z"),
        "last_event_time": latest_event.isoformat().replace("+00:00", "Z"),
        "last_receive_time": (
            latest_receive.isoformat().replace("+00:00", "Z")
            if latest_receive is not None
            else None
        ),
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "data_age_seconds": max(0.0, (observed_at - latest_event).total_seconds()),
        "latency_ms": median(latencies_ms) if latencies_ms else None,
        "latency_scope": "event_to_receive" if latencies_ms else None,
        "realtime_active": False,
    }


def _rolling_mean(values: Sequence[float], window: int, index: int) -> float | None:
    if index + 1 < window:
        return None
    return fmean(values[index + 1 - window : index + 1])


def serialize_candles(
    rows: Sequence[CanonicalCandle], *, limit: int
) -> list[dict[str, Any]]:
    """Serialize candles with causal SMA and ATR values for the UI."""

    if limit < 1:
        raise ValueError("limit must be positive")
    ordered = list(rows)
    closes = [row.close for row in ordered]
    true_ranges: list[float] = []
    for index, row in enumerate(ordered):
        prior_close = closes[index - 1] if index else row.close
        true_ranges.append(
            max(
                row.high - row.low,
                abs(row.high - prior_close),
                abs(row.low - prior_close),
            )
        )
    serialized: list[dict[str, Any]] = []
    for index, row in enumerate(ordered):
        serialized.append(
            {
                "event_time": row.event_time_utc.isoformat().replace("+00:00", "Z"),
                "session": row.session_date.isoformat(),
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "volume": row.volume,
                "sma_20": _rolling_mean(closes, 20, index),
                "sma_50": _rolling_mean(closes, 50, index),
                "sma_200": _rolling_mean(closes, 200, index),
                "atr_14": _rolling_mean(true_ranges, 14, index),
                "is_complete": row.is_complete,
            }
        )
    return serialized[-limit:]


def calculate_summary(
    rows: Sequence[CanonicalCandle],
) -> dict[str, float | dict[str, float | None] | None]:
    """Calculate the small set of derived values shown by the control room."""

    if not rows:
        raise ValueError("candle summary requires at least one row")
    closes = [row.close for row in rows]
    true_ranges: list[float] = []
    for index, row in enumerate(rows):
        prior_close = closes[index - 1] if index else row.close
        true_ranges.append(
            max(
                row.high - row.low,
                abs(row.high - prior_close),
                abs(row.low - prior_close),
            )
        )
    latest = rows[-1]
    previous_close: float | None = rows[-2].close if len(rows) > 1 else None
    change = latest.close - previous_close if previous_close is not None else None
    change_pct = (
        change / previous_close
        if change is not None and previous_close is not None
        else None
    )
    volume_window = [row.volume for row in rows[-20:]]
    volume_median = median(volume_window) if volume_window else None
    return {
        "latest": {
            "open": latest.open,
            "high": latest.high,
            "low": latest.low,
            "close": latest.close,
            "volume": latest.volume,
        },
        "change": change,
        "change_pct": change_pct,
        "session_range_pct": (latest.high - latest.low) / latest.close,
        "atr_14": fmean(true_ranges[-14:]) if len(true_ranges) >= 14 else None,
        "sma_20": fmean(closes[-20:]) if len(closes) >= 20 else None,
        "sma_50": fmean(closes[-50:]) if len(closes) >= 50 else None,
        "sma_200": fmean(closes[-200:]) if len(closes) >= 200 else None,
        "volume_vs_20_session_median": (
            latest.volume / volume_median if volume_median not in (None, 0) else None
        ),
    }
