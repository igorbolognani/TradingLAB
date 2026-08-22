import pytest

from tradinglab.dashboard_server import validate_battery_request


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
