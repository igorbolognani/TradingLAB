from datetime import UTC, datetime
from pathlib import Path

import pytest

from tradinglab.dashboard_server import canonical_candle_payload
from tradinglab.data import (
    inspect_canonical_candles,
    load_candle_csv,
    serialize_canonical_candles,
)


def _write_candle_file(path: Path) -> None:
    path.write_text(
        "timestamp_utc,symbol,interval,open,high,low,close,volume,provider,provider_version,receive_time_utc,is_complete,price_basis\n"
        "2025-01-02T14:30:00Z,SPY,1d,100,102,99,101,1000,licensed-test,2.0,2025-01-02T14:30:00.250Z,true,raw\n"
        "2025-01-03T14:30:00Z,SPY,1d,101,103,100,102,1100,licensed-test,2.0,2025-01-03T14:30:00.250Z,true,raw\n"
        "2025-01-06T14:30:00Z,SPY,1d,102,104,101,103,1200,licensed-test,2.0,2025-01-06T14:30:00.250Z,true,raw\n",
        encoding="utf-8",
    )


def test_canonical_candle_file_preserves_provider_clocks_and_latency(
    tmp_path: Path,
) -> None:
    path = tmp_path / "licensed_spy.csv"
    _write_candle_file(path)
    rows = load_candle_csv(path, symbol="SPY")

    quality = inspect_canonical_candles(
        rows,
        now=datetime(2025, 1, 6, 14, 31, tzinfo=UTC),
    )

    assert quality["status"] == "pass"
    assert quality["latency_ms"] == pytest.approx(250.0)
    assert quality["latency_scope"] == "event_to_receive"
    assert quality["realtime_active"] is False
    assert serialize_canonical_candles(rows, limit=2)[-1]["close"] == 103.0


def test_dashboard_can_serve_configured_file_without_yfinance(tmp_path: Path) -> None:
    path = tmp_path / "licensed_spy.csv"
    _write_candle_file(path)

    payload = canonical_candle_payload(path, symbol="SPY", limit=2)

    assert payload["source"]["provider"] == "licensed-test"
    assert payload["freshness"]["realtime_active"] is False
    assert payload["freshness"]["latency_ms"] == pytest.approx(250.0)
    assert payload["quality"]["manifest_validation"]["valid"] is True
    assert payload["calculated"]["latest"]["close"] == 103.0


def test_canonical_candle_file_rejects_ambiguous_time(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        "timestamp,symbol,open,high,low,close,volume\n"
        "2025-01-02,SPY,100,102,99,101,1000\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="UTC"):
        load_candle_csv(path)
