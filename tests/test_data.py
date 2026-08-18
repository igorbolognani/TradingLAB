import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from conftest import StaticSource, raw_provider_frame

from tradinglab.calendar import regular_sessions
from tradinglab.data import SnapshotStore, normalize_provider_frame
from tradinglab.data_source import ProviderFrame, RetrievalRequest
from tradinglab.hashing import canonical_json_bytes, sha256_bytes


def provider(frame: pd.DataFrame) -> ProviderFrame:
    return ProviderFrame(
        symbol="SPY",
        frame=frame,
        provider="fixture-provider",
        provider_version="1-test",
        exact_query_arguments={"explicit": True},
    )


def test_raw_actions_and_coherent_normalization_are_preserved(
    fixture_request: RetrievalRequest,
) -> None:
    raw = raw_provider_frame()
    original = raw.copy(deep=True)
    result = normalize_provider_frame(
        provider(raw),
        requested_start=fixture_request.start,
        requested_end_exclusive=fixture_request.end_exclusive,
    )
    pd.testing.assert_frame_equal(result.raw, original)
    pd.testing.assert_series_equal(result.actions["Dividends"], original["Dividends"])
    pd.testing.assert_series_equal(
        result.actions["Stock Splits"], original["Stock Splits"]
    )
    factor = original["Adj Close"].to_numpy() / original["Close"].to_numpy()
    for column in ("Open", "High", "Low", "Close"):
        np.testing.assert_allclose(
            result.normalized[column].to_numpy(), original[column].to_numpy() * factor
        )
    np.testing.assert_allclose(result.normalized["Close"], original["Adj Close"])
    assert "Adj Close" not in result.normalized.columns
    assert result.missing_session_diagnostics["forward_fill_applied"] is False


def test_calendar_is_explicitly_materialized_for_2005_warmup() -> None:
    sessions = regular_sessions(date(2005, 1, 1), date(2005, 1, 10))
    assert sessions[0].date() == date(2005, 1, 3)
    assert sessions[-1].date() == date(2005, 1, 10)


def test_normalization_is_deterministic(fixture_request: RetrievalRequest) -> None:
    frame = raw_provider_frame()
    first = normalize_provider_frame(
        provider(frame),
        requested_start=fixture_request.start,
        requested_end_exclusive=fixture_request.end_exclusive,
    )
    second = normalize_provider_frame(
        provider(frame),
        requested_start=fixture_request.start,
        requested_end_exclusive=fixture_request.end_exclusive,
    )
    pd.testing.assert_frame_equal(first.normalized, second.normalized)
    assert first.missing_session_diagnostics == second.missing_session_diagnostics


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda frame: frame.iloc[::-1], "chronological"),
        (lambda frame: pd.concat([frame, frame.iloc[[-1]]]), "unique"),
        (lambda frame: frame.drop(columns=["Adj Close"]), "missing required"),
        (lambda frame: frame.assign(Open=0.0), "strictly positive"),
        (lambda frame: frame.assign(Volume=-1), "nonnegative"),
        (lambda frame: frame.assign(High=1.0), "OHLC"),
    ],
)
def test_invalid_required_market_data_fails(
    fixture_request: RetrievalRequest, mutation: object, match: str
) -> None:
    frame = mutation(raw_provider_frame())  # type: ignore[operator]
    with pytest.raises(ValueError, match=match):
        normalize_provider_frame(
            provider(frame),
            requested_start=fixture_request.start,
            requested_end_exclusive=fixture_request.end_exclusive,
        )


def test_2026_row_is_never_accepted() -> None:
    frame = raw_provider_frame(date(2025, 12, 31), date(2025, 12, 31))
    extra = frame.copy()
    extra.index = pd.DatetimeIndex([pd.Timestamp("2026-01-02", tz="America/New_York")])
    with pytest.raises(ValueError, match="2026 observation"):
        normalize_provider_frame(
            provider(pd.concat([frame, extra])),
            requested_start=date(2025, 12, 31),
            requested_end_exclusive=date(2026, 1, 1),
        )


def test_missing_session_diagnostics_are_explicit() -> None:
    frame = raw_provider_frame(omit=date(2025, 1, 7))
    result = normalize_provider_frame(
        provider(frame),
        requested_start=date(2025, 1, 2),
        requested_end_exclusive=date(2025, 1, 11),
    )
    diagnostics = result.missing_session_diagnostics
    assert diagnostics["missing_session_count"] == 1
    assert diagnostics["missing_sessions"] == ["2025-01-07"]


def test_snapshot_manifest_hashes_ranges_and_refresh_identity(
    tmp_path: Path,
    fixture_request: RetrievalRequest,
    static_source: StaticSource,
) -> None:
    store = SnapshotStore(tmp_path, source=static_source)
    first = store.fetch_dataset(fixture_request)
    second = store.fetch_dataset(fixture_request)
    assert first["dataset_id"] != second["dataset_id"]
    assert first["checksums"] == second["checksums"]
    assert first["dataset_checksum"] == second["dataset_checksum"]
    assert first["manifest_hash"] != second["manifest_hash"]
    assert first["requested_start"] == "2025-01-02"
    assert first["requested_end_exclusive"] == "2025-01-11"
    assert first["effective_first_session"]["SPY"] == "2025-01-02"
    assert first["effective_last_session"]["SPY"] == "2025-01-10"
    assert first["raw_schema"]["SPY"][:6] == [
        "Open",
        "High",
        "Low",
        "Close",
        "Adj Close",
        "Volume",
    ]
    assert store.validate_dataset(first["dataset_id"])["valid"] is True
    normalized = store.load_normalized(first["dataset_id"], "SPY")
    assert pd.DatetimeIndex(normalized.index).tz is not None
    assert normalized.index.max().year == 2025


def test_snapshot_corruption_is_detected(
    tmp_path: Path,
    fixture_request: RetrievalRequest,
    static_source: StaticSource,
) -> None:
    store = SnapshotStore(tmp_path, source=static_source)
    manifest = store.fetch_dataset(fixture_request)
    path = (
        tmp_path / manifest["dataset_id"] / manifest["file_paths"]["SPY"]["normalized"]
    )
    path.write_text(path.read_text(encoding="utf-8") + "corrupt\n", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        store.validate_dataset(manifest["dataset_id"])


def test_snapshot_manifest_metadata_tampering_is_detected(
    tmp_path: Path,
    fixture_request: RetrievalRequest,
    static_source: StaticSource,
) -> None:
    store = SnapshotStore(tmp_path, source=static_source)
    manifest = store.fetch_dataset(fixture_request)
    path = tmp_path / manifest["dataset_id"] / "manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["provider_version"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="provenance hash mismatch"):
        store.validate_dataset(str(manifest["dataset_id"]))


def test_snapshot_identity_binds_query_metadata_even_after_manifest_rehash(
    tmp_path: Path,
    fixture_request: RetrievalRequest,
    static_source: StaticSource,
) -> None:
    store = SnapshotStore(tmp_path, source=static_source)
    manifest = store.fetch_dataset(fixture_request)
    path = tmp_path / manifest["dataset_id"] / "manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["exact_query_arguments"]["auto_adjust"] = True
    unhashed = {key: value for key, value in payload.items() if key != "manifest_hash"}
    payload["manifest_hash"] = sha256_bytes(canonical_json_bytes(unhashed))
    path.write_bytes(canonical_json_bytes(payload))
    with pytest.raises(ValueError, match="identity does not match"):
        store.validate_dataset(str(manifest["dataset_id"]))


def test_snapshot_roundtrip_handles_mixed_est_and_edt_offsets(tmp_path: Path) -> None:
    frame = raw_provider_frame(date(2025, 1, 2), date(2025, 7, 2))
    request = RetrievalRequest(
        symbols=("SPY",),
        start=date(2025, 1, 2),
        end_exclusive=date(2025, 7, 3),
    )
    store = SnapshotStore(tmp_path, source=StaticSource(frame))
    manifest = store.fetch_dataset(request)
    loaded = store.load_normalized(str(manifest["dataset_id"]), "SPY")
    assert str(loaded.index[0].utcoffset()) == "-1 day, 19:00:00"
    assert str(loaded.index[-1].utcoffset()) == "-1 day, 20:00:00"
    assert store.validate_dataset(str(manifest["dataset_id"]))["valid"] is True
