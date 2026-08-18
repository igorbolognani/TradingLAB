"""Deterministic raw/actions/normalized transformation and quality checks."""

from dataclasses import dataclass
from datetime import date
from io import StringIO
from typing import Any

import numpy as np
import pandas as pd

from tradinglab.calendar import normalize_daily_index, regular_sessions
from tradinglab.constants import NORMALIZATION_FORMULA, NORMALIZATION_VERSION
from tradinglab.data_source import ProviderFrame

RAW_REQUIRED_COLUMNS: tuple[str, ...] = (
    "Open",
    "High",
    "Low",
    "Close",
    "Adj Close",
    "Volume",
)
ACTION_COLUMNS: tuple[str, ...] = ("Dividends", "Stock Splits", "Capital Gains")
NORMALIZED_COLUMNS: tuple[str, ...] = (
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "AdjustmentFactor",
)


@dataclass(frozen=True)
class NormalizedFrames:
    """Three explicit immutable dataset layers plus diagnostics."""

    raw: pd.DataFrame
    actions: pd.DataFrame
    normalized: pd.DataFrame
    source_timezone: str
    missing_values: dict[str, dict[str, int]]
    missing_session_diagnostics: dict[str, Any]


def _validate_ohlcv(frame: pd.DataFrame, *, adjusted_close: bool) -> None:
    required = RAW_REQUIRED_COLUMNS if adjusted_close else NORMALIZED_COLUMNS[:5]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required market columns: {missing}")
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError("session index must be chronological and unique")
    price_columns = ["Open", "High", "Low", "Close"]
    if adjusted_close:
        price_columns.append("Adj Close")
    prices = frame[price_columns].apply(pd.to_numeric, errors="coerce")
    if prices.isna().any().any():
        raise ValueError("required prices contain missing or nonnumeric values")
    if not (prices > 0).all().all():
        raise ValueError("all raw and normalized prices must be strictly positive")
    volume = pd.to_numeric(frame["Volume"], errors="coerce")
    if volume.isna().any() or (volume < 0).any():
        raise ValueError("volume must be present and nonnegative")
    if (prices["High"] < prices[["Open", "Close", "Low"]].max(axis=1)).any() or (
        prices["Low"] > prices[["Open", "Close", "High"]].min(axis=1)
    ).any():
        raise ValueError("invalid OHLC relationship")


def _missing_values(frame: pd.DataFrame) -> dict[str, int]:
    return {str(column): int(count) for column, count in frame.isna().sum().items()}


def _session_diagnostics(
    index: pd.DatetimeIndex, requested_start: date, requested_end_exclusive: date
) -> dict[str, Any]:
    expected = regular_sessions(requested_start, requested_end_exclusive)
    expected = expected[expected < pd.Timestamp(requested_end_exclusive, tz=index.tz)]
    missing = expected.difference(index)
    unexpected = index.difference(expected)
    return {
        "expected_session_count": len(expected),
        "accepted_session_count": len(index),
        "missing_session_count": len(missing),
        "missing_sessions": [value.date().isoformat() for value in missing],
        "unexpected_session_count": len(unexpected),
        "unexpected_sessions": [value.date().isoformat() for value in unexpected],
        "forward_fill_applied": False,
    }


def normalize_provider_frame(
    provider: ProviderFrame,
    *,
    requested_start: date,
    requested_end_exclusive: date,
) -> NormalizedFrames:
    """Create coherent total-return OHLC without mutating provider output."""

    raw = provider.frame.copy(deep=True)
    normalized_index, source_timezone = normalize_daily_index(raw.index)
    validation_view = raw.copy(deep=True)
    validation_view.index = normalized_index
    _validate_ohlcv(validation_view, adjusted_close=True)
    if validation_view.index.max().year >= 2026:
        raise ValueError("a 2026 observation was returned and cannot be accepted")

    expected = regular_sessions(requested_start, requested_end_exclusive)
    accepted = set(validation_view.index)
    expected_set = set(expected)
    unexpected = [session for session in accepted if session not in expected_set]
    if unexpected:
        raise ValueError(
            f"provider returned non-XNYS or out-of-range sessions: {unexpected}"
        )

    factor = validation_view["Adj Close"] / validation_view["Close"]
    if factor.isna().any() or (factor <= 0).any() or not np.isfinite(factor).all():
        raise ValueError("the OHLC adjustment factor must be finite and positive")
    normalized = pd.DataFrame(index=normalized_index)
    for column in ("Open", "High", "Low", "Close"):
        normalized[column] = validation_view[column].astype(float) * factor
    normalized["Volume"] = validation_view["Volume"]
    normalized["AdjustmentFactor"] = factor
    normalized = normalized.loc[:, list(NORMALIZED_COLUMNS)]
    _validate_ohlcv(normalized, adjusted_close=False)
    if not np.allclose(
        normalized["Close"].to_numpy(),
        validation_view["Adj Close"].to_numpy(),
        rtol=1e-12,
        atol=1e-10,
    ):
        raise ValueError("normalized Close does not reconcile with provider Adj Close")

    actions = pd.DataFrame(index=raw.index.copy())
    for column in ACTION_COLUMNS:
        actions[column] = raw[column] if column in raw.columns else 0.0
    diagnostics = _session_diagnostics(
        normalized_index, requested_start, requested_end_exclusive
    )
    return NormalizedFrames(
        raw=raw,
        actions=actions,
        normalized=normalized,
        source_timezone=source_timezone,
        missing_values={
            "raw": _missing_values(raw),
            "actions": _missing_values(actions),
            "normalized": _missing_values(normalized),
        },
        missing_session_diagnostics=diagnostics,
    )


def dataframe_csv_bytes(frame: pd.DataFrame, *, index_label: str) -> bytes:
    """Serialize a frame with stable order, line endings, and round-trip precision."""

    buffer = StringIO()
    frame.to_csv(
        buffer,
        index=True,
        index_label=index_label,
        lineterminator="\n",
        float_format="%.17g",
        date_format="%Y-%m-%dT%H:%M:%S%z",
    )
    return buffer.getvalue().encode("utf-8")


def normalization_contract() -> dict[str, str]:
    """Return the versioned formula embedded in every dataset manifest."""

    return {
        "normalization_version": NORMALIZATION_VERSION,
        "normalization_formula": NORMALIZATION_FORMULA,
    }
