from datetime import date
from pathlib import Path

import pytest
from conftest import StaticSource, raw_provider_frame

from tradinglab.dashboard_server import candle_payload, validate_battery_request
from tradinglab.data import SnapshotStore
from tradinglab.data_source import RetrievalRequest


def test_dashboard_api_allows_only_confirmed_non_holdout_batteries() -> None:
    dataset_id = "ds_local_dataset_1"
    assert validate_battery_request(
        {
            "confirmed": True,
            "dataset_id": dataset_id,
            "splits": ["development", "validation_oos"],
        },
        [dataset_id],
    ) == (dataset_id, ("development", "validation_oos"))


@pytest.mark.parametrize(
    "payload",
    [
        {
            "confirmed": False,
            "dataset_id": "ds_local_dataset_1",
            "splits": ["development"],
        },
        {
            "confirmed": True,
            "dataset_id": "ds_local_dataset_1",
            "splits": ["project_holdout"],
        },
        {"confirmed": True, "dataset_id": "ds_local_dataset_1", "splits": []},
    ],
)
def test_dashboard_api_rejects_unsafe_requests(payload: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        validate_battery_request(payload, ["ds_local_dataset_1"])


def test_dashboard_api_rejects_path_like_dataset_ids() -> None:
    with pytest.raises(ValueError, match="dataset_id"):
        validate_battery_request(
            {
                "confirmed": True,
                "dataset_id": "../snapshots",
                "splits": ["development"],
            },
            ["../snapshots"],
        )


def test_candle_endpoint_returns_verified_real_snapshot_rows(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "data" / "snapshots"
    store = SnapshotStore(snapshot_root, source=StaticSource(raw_provider_frame()))
    manifest = store.fetch_dataset(
        RetrievalRequest(
            symbols=("SPY",),
            start=date(2025, 1, 2),
            end_exclusive=date(2025, 1, 11),
        )
    )

    payload = candle_payload(
        tmp_path,
        dataset_id=str(manifest["dataset_id"]),
        symbol="SPY",
        limit=2,
    )

    assert payload["returned_row_count"] == 2
    assert len(payload["candles"]) == 2
    assert payload["source"]["provider"] == "fixture-provider"
    assert payload["source"]["dataset_checksum"] == manifest["dataset_checksum"]
    assert payload["freshness"]["realtime_active"] is False
    assert payload["quality"]["manifest_validation"]["valid"] is True
    assert payload["calculated"]["latest"]["close"] is not None
