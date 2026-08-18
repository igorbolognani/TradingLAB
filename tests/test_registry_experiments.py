import json
import os
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest
from conftest import SPEC_DIR, StaticSource, raw_provider_frame

from tradinglab.constants import ASSETS
from tradinglab.data import SnapshotStore
from tradinglab.data_source import RetrievalRequest
from tradinglab.experiments import (
    ExperimentRunner,
    TrialRequest,
    _assert_development_validation_readiness,
    _configuration_id,
    battery_configurations,
    completed_experiment_rows,
    new_experiment_id,
    run_battery,
)
from tradinglab.registry import TrialRegistry, utc_now
from tradinglab.reports import aggregate_report


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


def test_registry_marks_holdout_seen_irreversibly(tmp_path: Path) -> None:
    registry = TrialRegistry(tmp_path / "events.jsonl")
    assert registry.holdout_seen() is False
    registry.append(
        {
            "event_type": "holdout_seen",
            "created_at": utc_now(),
            "experiment_id": "exp-final",
        }
    )
    assert registry.holdout_seen() is True


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


def mini_project(
    tmp_path: Path, project_root: Path, *, validation_warmup: bool = True
) -> tuple[Path, str]:
    project = tmp_path / "project"
    project.mkdir()
    _git(project, "init", "-b", "main")
    shutil.copy(project_root / "uv.lock", project / "uv.lock")
    shutil.copy(project_root / ".gitignore", project / ".gitignore")
    shutil.copytree(SPEC_DIR, project / "strategy_specs")
    _git(project, "add", ".gitignore", "uv.lock", "strategy_specs")
    _git(project, "commit", "-m", "fixture")
    start = date(2014, 12, 19) if validation_warmup else date(2020, 1, 2)
    end = date(2015, 1, 9) if validation_warmup else date(2020, 1, 10)
    frame = raw_provider_frame(start, end)
    store = SnapshotStore(project / "data" / "snapshots", source=StaticSource(frame))
    manifest = store.fetch_dataset(
        RetrievalRequest(
            symbols=("SPY",),
            start=start,
            end_exclusive=date(2015, 1, 10) if validation_warmup else date(2020, 1, 11),
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
        split_key="validation_oos",
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
    reproduction = runner.reproduce(first.trial_id)
    assert reproduction == {
        "trial_id": first.trial_id,
        "analytical_equivalence": True,
        "provenance_match": True,
        "artifacts_intact": True,
        "reproduced": True,
        "reasons": [],
    }
    for name in (
        "manifest.json",
        "metrics.csv",
        "trades.csv",
        "equity_curve.csv",
        "signals.csv",
        "report.md",
        "plots/equity_curve.png",
        "artifact_inventory.json",
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
        "dataset_manifest_hash",
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
    assert {
        "canonical_completed_lifecycles",
        "canonical_final_equity",
        "closed_trade_rows",
        "final_equity_delta_usd",
        "native_final_equity",
        "reconciles_within_one_microdollar",
    }.issubset(first.manifest["engine_reference"])
    assert first.manifest["engine_reference"]["reconciles_within_one_microdollar"]
    assert runner.registry.holdout_seen() is False

    _git(project, "commit", "--allow-empty", "-m", "changed provenance")
    changed_code_state = runner.reproduce(first.trial_id)
    assert changed_code_state["analytical_equivalence"] is True
    assert changed_code_state["provenance_match"] is False
    assert changed_code_state["reproduced"] is False
    assert "git_commit differs from the recorded trial" in changed_code_state["reasons"]

    (first.artifact_dir / "report.md").write_text("tampered\n", encoding="utf-8")
    tampered = runner.reproduce(first.trial_id)
    assert tampered["analytical_equivalence"] is True
    assert tampered["artifacts_intact"] is False
    assert tampered["reproduced"] is False
    assert "artifact hash differs: report.md" in tampered["reasons"]


def test_direct_holdout_trial_is_blocked_before_registry_write(
    tmp_path: Path, project_root: Path
) -> None:
    project, dataset_id = mini_project(tmp_path, project_root)
    runner = ExperimentRunner(project)
    with pytest.raises(ValueError, match="controlled battery gate"):
        runner.run_trial(
            TrialRequest(
                spec_path=project / "strategy_specs" / "BUY_HOLD_V1.yaml",
                dataset_id=dataset_id,
                asset="SPY",
                split_key="project_holdout",
                parameters={},
                friction_bps=5,
                purpose="primary",
                experiment_id=new_experiment_id(),
            )
        )
    assert runner.registry.events() == []


def test_holdout_battery_requires_complete_development_and_validation(
    tmp_path: Path, project_root: Path
) -> None:
    project, dataset_id = mini_project(tmp_path, project_root)
    with pytest.raises(ValueError, match="development is not the exact complete"):
        run_battery(
            project,
            dataset_id=dataset_id,
            split_keys=("project_holdout",),
            confirm_holdout=True,
            experiment_id=new_experiment_id(),
        )
    assert TrialRegistry(project / "registry" / "events.jsonl").events() == []


def test_holdout_readiness_requires_exact_complete_ordered_batteries() -> None:
    events: list[dict[str, object]] = []
    for split in ("development", "validation_oos"):
        for asset in ASSETS:
            for index, (strategy, parameters, friction, purpose) in enumerate(
                battery_configurations()
            ):
                trial_id = f"{split}-{asset}-{index}"
                common = {
                    "trial_id": trial_id,
                    "temporal_split": split,
                    "configuration_id": _configuration_id(
                        asset,
                        split,
                        strategy,
                        parameters,
                        friction,
                        purpose,
                    ),
                }
                events.append({**common, "event_type": "started"})
                events.append({**common, "event_type": "completed"})
    _assert_development_validation_readiness(events)

    duplicated = [*events, dict(events[-1])]
    with pytest.raises(ValueError, match="exact complete closed battery"):
        _assert_development_validation_readiness(duplicated)

    reordered = [events[-2], *events[:-2], events[-1]]
    with pytest.raises(ValueError, match=r"Validation|validation began"):
        _assert_development_validation_readiness(reordered)


def test_non_control_requires_matching_registered_buy_hold(
    tmp_path: Path, project_root: Path
) -> None:
    project, dataset_id = mini_project(tmp_path, project_root)
    runner = ExperimentRunner(project)
    experiment_id = new_experiment_id()
    benchmark = runner.run_trial(
        TrialRequest(
            spec_path=project / "strategy_specs" / "BUY_HOLD_V1.yaml",
            dataset_id=dataset_id,
            asset="SPY",
            split_key="validation_oos",
            parameters={},
            friction_bps=5,
            purpose="primary",
            experiment_id=experiment_id,
        )
    )
    before = len(runner.registry.events())
    with pytest.raises(ValueError, match="matching Buy & Hold trial id"):
        runner.run_trial(
            TrialRequest(
                spec_path=project / "strategy_specs" / "TREND_SMA200_V1.yaml",
                dataset_id=dataset_id,
                asset="SPY",
                split_key="validation_oos",
                parameters={"sma": 150},
                friction_bps=5,
                purpose="parameter_sensitivity",
                experiment_id=experiment_id,
            )
        )
    assert len(runner.registry.events()) == before
    candidate = runner.run_trial(
        TrialRequest(
            spec_path=project / "strategy_specs" / "TREND_SMA200_V1.yaml",
            dataset_id=dataset_id,
            asset="SPY",
            split_key="validation_oos",
            parameters={"sma": 150},
            friction_bps=5,
            purpose="parameter_sensitivity",
            experiment_id=experiment_id,
            benchmark_trial_id=benchmark.trial_id,
        )
    )
    assert candidate.manifest["benchmark_trial_id"] == benchmark.trial_id
    assert set(candidate.manifest["benchmark_deltas"]) == {
        "delta_CAGR_vs_buy_hold",
        "delta_Sharpe_vs_buy_hold",
        "delta_max_drawdown_vs_buy_hold",
    }
    assert runner.reproduce(candidate.trial_id)["reproduced"] is True


@pytest.mark.parametrize(
    ("purpose", "evidence_class"),
    [
        ("debug", "debug_non_evidence"),
        ("synthetic", "synthetic_non_market"),
    ],
)
def test_debug_and_synthetic_trials_are_explicitly_non_evidence(
    tmp_path: Path,
    project_root: Path,
    purpose: str,
    evidence_class: str,
) -> None:
    project, dataset_id = mini_project(tmp_path, project_root)
    outcome = ExperimentRunner(project).run_trial(
        TrialRequest(
            spec_path=project / "strategy_specs" / "BUY_HOLD_V1.yaml",
            dataset_id=dataset_id,
            asset="SPY",
            split_key="validation_oos",
            parameters={},
            friction_bps=5,
            purpose=purpose,  # type: ignore[arg-type]
            experiment_id=new_experiment_id(),
        )
    )
    assert outcome.manifest["evidence_class"] == evidence_class
    assert outcome.manifest["historical_evidence_only"] is False


def test_aggregate_report_detects_existing_artifact_tampering(
    tmp_path: Path, project_root: Path
) -> None:
    project, dataset_id = mini_project(tmp_path, project_root)
    runner = ExperimentRunner(project)
    experiment_id = new_experiment_id()
    runner.run_trial(
        TrialRequest(
            spec_path=project / "strategy_specs" / "BUY_HOLD_V1.yaml",
            dataset_id=dataset_id,
            asset="SPY",
            split_key="validation_oos",
            parameters={},
            friction_bps=5,
            purpose="primary",
            experiment_id=experiment_id,
        )
    )
    rows = completed_experiment_rows(project, runner.registry, experiment_id)
    report = aggregate_report(
        rows,
        project / "artifacts" / "reports",
        experiment_id,
        runner.registry.events(),
    )
    (report / "report.md").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="report artifact changed"):
        aggregate_report(
            rows,
            project / "artifacts" / "reports",
            experiment_id,
            runner.registry.events(),
        )


def test_failed_trial_is_preserved_with_started_and_failed_events(
    tmp_path: Path, project_root: Path
) -> None:
    project, dataset_id = mini_project(tmp_path, project_root, validation_warmup=False)
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
