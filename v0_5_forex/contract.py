"""A broker-neutral UTC daily-bar contract for the V0.5 Forex pilot."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

REQUIRED_COLUMNS = frozenset(
    {"timestamp_utc", "open", "high", "low", "close", "volume"}
)


def _parse_utc(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(f"invalid UTC timestamp: {value}") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("Forex timestamps must explicitly use UTC")
    return parsed.astimezone(UTC)


def _price(value: float, field_name: str) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field_name} must be finite and positive")


@dataclass(frozen=True, slots=True)
class ForexBar:
    """One broker-neutral daily bar with an explicit UTC timestamp."""

    timestamp_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str = "EURUSD"
    source: str = "offline-fixture"

    def validate(self) -> None:
        if (
            self.timestamp_utc.tzinfo is None
            or self.timestamp_utc.utcoffset() != timedelta(0)
        ):
            raise ValueError("ForexBar.timestamp_utc must be timezone-aware UTC")
        if not self.symbol or not self.source:
            raise ValueError("ForexBar symbol and source are required")
        for field_name in ("open", "high", "low", "close"):
            _price(float(getattr(self, field_name)), field_name)
        if self.high < max(self.open, self.close):
            raise ValueError("high must not be below open or close")
        if self.low > min(self.open, self.close):
            raise ValueError("low must not be above open or close")
        if not math.isfinite(self.volume) or self.volume < 0:
            raise ValueError("volume must be finite and non-negative")


def load_csv(
    path: Path, *, symbol: str = "EURUSD", source: str = "offline-csv"
) -> list[ForexBar]:
    """Load a source-controlled or user-supplied UTC CSV without network I/O."""

    bars: list[ForexBar] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = frozenset(reader.fieldnames or ())
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"Forex CSV is missing columns: {sorted(missing)}")
        for row in reader:
            bar = ForexBar(
                timestamp_utc=_parse_utc(row["timestamp_utc"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                symbol=symbol,
                source=source,
            )
            bar.validate()
            bars.append(bar)
    if not bars:
        raise ValueError("Forex CSV contains no bars")
    timestamps = [bar.timestamp_utc for bar in bars]
    if timestamps != sorted(timestamps):
        raise ValueError("Forex bars must be chronological")
    if len(set(timestamps)) != len(timestamps):
        raise ValueError("Forex bars must not contain duplicate timestamps")
    return bars
