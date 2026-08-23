"""Immutable snapshot and coherent normalization contracts."""

from tradinglab.data.candles import (
    CANONICAL_CANDLE_SCHEMA,
    CanonicalCandle,
    calculate_summary,
    load_candle_csv,
)
from tradinglab.data.candles import (
    inspect_candles as inspect_canonical_candles,
)
from tradinglab.data.candles import (
    serialize_candles as serialize_canonical_candles,
)
from tradinglab.data.normalization import NormalizedFrames, normalize_provider_frame
from tradinglab.data.quality import (
    calculate_candle_summary,
    inspect_candles,
    serialize_candles,
)
from tradinglab.data.snapshots import SnapshotStore

__all__ = [
    "CANONICAL_CANDLE_SCHEMA",
    "CanonicalCandle",
    "NormalizedFrames",
    "SnapshotStore",
    "calculate_candle_summary",
    "calculate_summary",
    "inspect_candles",
    "inspect_canonical_candles",
    "load_candle_csv",
    "normalize_provider_frame",
    "serialize_candles",
    "serialize_canonical_candles",
]
