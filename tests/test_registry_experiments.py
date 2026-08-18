import json
import os
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest
from conftest import SPEC_DIR, StaticSource, raw_provider_frame

from tradinglab.data import SnapshotStore
from tradinglab.data_source import RetrievalRequest
from tradinglab.experiments import ExperimentRunner, TrialRequest, new_experiment_id
from tradinglab.registry import TrialRegistry, utc_now


def test_registry_appends_without_mutating_prior_bytes(tmp_path: Path) -> None:
    registry = TrialRegistry(tmp_path / "events.jsonl")
    registry.append(
        {"event_type": "started", "created_at": utc_now(), "trial_id": "t1"}
    )
    first = registry.path.read_bytes()
    registry.append(
        {"event_type": "completed", "created_at": utc_now(), "trial_id": "t1"}
    )
    second = registry.path.read_bytes()
    assert second.startswith(first)
    assert [event["event_type"] for event in registry.events_for_trial("t1")] == [
        "started",
        "completed",
    ]


def _git(project: Path, *args: str) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
    }
    subprocess.run(
        ["git", *args], cwd=project, check=True, capture_output=True, env=env
    )


def mini_project(tmp_path: Path, project_root: Path) -> tuple[Path, str]:
    project = tmp_path / "project"
    project.mkdir()
    _git(project, "init", "-b", "main")
    shutil.copy(project_root / "uv.lock", project / "uv.lock")
    shutil.copytree(SPEC_DIR, project / "strategy_specs")
    _git(project, "add", "uv.lock", "strategy_specs")
    _git(project, "commit", "-m", "fixture")
    frame = raw_provider_frame(date(2020, 1, 2), date(2020, 1, 10))
    store = SnapshotStore(project / "data" / "snapshots", source=StaticSource(frame))
    manifest = store.fetch_dataset(
        RetrievalRequest(
            symbols=("SPY",), start=date(2020, 1, 2), end_exclusive=date(2020, 1, 11)
        )
    )
    return project, str(manifest["dataset_id"])


def test_completed_trial_manifest_artifacts_immutability_and_reproduction(
    tmp_path: Path, project_root: Path
) -> None:
    project, dataset_id = mini_project(tmp_path, project_root)
    runner = ExperimentRunner(project)
    experiment_id = new_experiment_id()
    request = TrialRequest(
        spec_path=project / "strategy_specs" / "BUY_HOLD_V1.yaml",
        dataset_id=dataset_id,
        asset="SPY",
        split_key="project_holdout",
        parameters={},
        friction_bps=5,
        purpose="primary",
        experiment_id=experiment_id,
    )
    first = runner.run_trial(request)
    second = runner.run_trial(request)
    assert first.trial_id != second.trial_id
    assert first.artifact_dir != second.artifact_dir
    assert (
        first.manifest["canonical_analytical_hash"]
        == second.manifest["canonical_analytical_hash"]
    )
    assert runner.reproduce(first.trial_id) is True
    for name in (
        "manifest.json",
        "metrics.csv",
        "trades.csv",
        "equity_curve.csv",
        "signals.csv",
        "report.md",
        "plots/equity_curve.png",
    ):
        assert (first.artifact_dir / name).is_file()
    required = {
        "trial_id",
        "experiment_id",
        "spec_hash",
        "git_commit",
        "git_branch",
        "dirty_worktree",
        "dirty_paths",
        "python_version",
        "dependency_lock_hash",
        "engine_name",
        "engine_version",
        "dataset_id",
        "dataset_checksum",
        "asset",
        "temporal_split",
        "parameters",
        "friction_bps",
        "price_basis",
        "execution_assumptions",
        "terminal_convention",
        "artifact_paths",
        "canonical_analytical_hash",
    }
    assert required.issubset(first.manifest)
    assert runner.registry.holdout_seen() is True


def test_failed_trial_is_preserved_with_started_and_failed_events(
    tmp_path: Path, project_root: Path
) -> None:
    project, dataset_id = mini_project(tmp_path, project_root)
    runner = ExperimentRunner(project)
    with pytest.raises(ValueError, match="no rows"):
        runner.run_trial(
            TrialRequest(
                spec_path=project / "strategy_specs" / "BUY_HOLD_V1.yaml",
                dataset_id=dataset_id,
                asset="SPY",
                split_key="development",
                parameters={},
                friction_bps=5,
                purpose="debug",
                experiment_id=new_experiment_id(),
            )
        )
    trial_events: dict[str, list[str]] = {}
    for event in runner.registry.events():
        if "trial_id" in event:
            trial_events.setdefault(event["trial_id"], []).append(event["event_type"])
    assert list(trial_events.values()) == [["started", "failed"]]
    failed_trial_id = next(iter(trial_events))
    manifest = json.loads(
        (
            project / "artifacts" / "trials" / failed_trial_id / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["status"] == "failed"
