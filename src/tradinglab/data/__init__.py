"""Immutable snapshot and coherent normalization contracts."""

from tradinglab.data.normalization import NormalizedFrames, normalize_provider_frame
from tradinglab.data.quality import (
    calculate_candle_summary,
    inspect_candles,
    serialize_candles,
)
from tradinglab.data.snapshots import SnapshotStore

__all__ = [
    "NormalizedFrames",
    "SnapshotStore",
    "calculate_candle_summary",
    "inspect_candles",
    "normalize_provider_frame",
    "serialize_candles",
]
