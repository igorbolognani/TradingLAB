"""Run and validate the frozen primary battery in the real LEAN engine.

The runner stages a clean copy for every invocation.  This prevents LEAN's
output/code copy from becoming input to the next invocation and makes a
partial battery resumable without treating a failed run as evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .contract import (
    ASSETS,
    DEFAULT_FRICTION_BPS,
    PRIMARY_PARAMETERS,
    SPLITS,
    STRATEGIES,
)
from .core import load_normalized_csv, replay

LEAN_CLI = ("uvx", "--from", "lean==1.0.228", "lean")
DEFAULT_IMAGE = "quantconnect/lean:17998"


@dataclass(frozen=True)
class EngineEvent:
    event: str
    session: str | None = None
    fill_session: str | None = None
    action: str | None = None
    reason: str | None = None
    indicator: float | None = None
    quantity: float | None = None
    price: float | None = None


@dataclass(frozen=True)
class EngineRun:
    asset: str
    split: str
    strategy_id: str
    friction_bps: int
    returncode: int
    status: str
    runtime_error: str
    output_dir: str
    events: tuple[EngineEvent, ...]


def _project_copy(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("output", "__pycache__", "*.pyc"),
    )


def _summary(output_dir: Path) -> dict:
    summaries = sorted(output_dir.glob("*-summary.json"))
    if not summaries:
        return {"state": {"Status": "Missing", "RuntimeError": "summary not found"}}
    return json.loads(summaries[0].read_text(encoding="utf-8"))


def _events(output_dir: Path) -> tuple[EngineEvent, ...]:
    logs = sorted(output_dir.glob("*-log.txt"))
    if not logs:
        return ()
    parsed: list[EngineEvent] = []
    for line in logs[0].read_text(encoding="utf-8", errors="replace").splitlines():
        start = line.find("{")
        if start < 0:
            continue
        payload = line[start:]
        try:
            item = json.loads(payload)
        except json.JSONDecodeError:
            continue
        parsed.append(
            EngineEvent(
                event=str(item.get("event", "")),
                session=item.get("session"),
                fill_session=item.get("fill_session"),
                action=item.get("action"),
                reason=item.get("reason"),
                indicator=item.get("indicator"),
                quantity=item.get("quantity"),
                price=item.get("price"),
            )
        )
    return tuple(parsed)


def run_one(
    *,
    project_root: Path,
    artifact_root: Path,
    asset: str,
    split: str,
    strategy_id: str,
    friction_bps: int = DEFAULT_FRICTION_BPS,
    image: str = DEFAULT_IMAGE,
    timeout_seconds: int = 300,
) -> EngineRun:
    """Run one LEAN invocation and preserve its output under ``artifact_root``."""

    key = f"{asset}__{split}__{strategy_id}"
    destination = artifact_root / key
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Docker may create root-owned __pycache__ files in the stage.  Keep the
    # stage in /tmp rather than making cleanup a source of false failures.
    temporary = tempfile.mkdtemp(prefix="tradinglab-lean-")
    try:
        stage = Path(temporary) / "project"
        _project_copy(project_root, stage)
        output = stage / "output" / "run"
        command = [
            *LEAN_CLI,
            "backtest",
            str(stage),
            "--no-update",
            "--image",
            image,
            "--lean-config",
            str(stage / "lean.json"),
            "--extra-docker-config",
            json.dumps({"user": f"{os.getuid()}:{os.getgid()}"}),
            "--output",
            str(output),
            "--parameter",
            "asset",
            asset,
            "--parameter",
            "split",
            split,
            "--parameter",
            "strategy_id",
            strategy_id,
            "--parameter",
            "friction_bps",
            str(friction_bps),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            returncode = completed.returncode
        except subprocess.TimeoutExpired:
            returncode = 124
        if destination.exists():
            shutil.rmtree(destination)
        if output.exists():
            shutil.copytree(output, destination)
    except BaseException:
        raise

    summary = _summary(destination)
    state = summary.get("state", {})
    return EngineRun(
        asset=asset,
        split=split,
        strategy_id=strategy_id,
        friction_bps=friction_bps,
        returncode=returncode,
        status=str(state.get("Status", "Missing")),
        runtime_error=str(state.get("RuntimeError", "")),
        output_dir=str(destination),
        events=_events(destination),
    )


def _event_mismatch(actual: EngineRun, bars_path: Path) -> list[str]:
    result = replay(
        load_normalized_csv(bars_path),
        asset=actual.asset,
        split=actual.split,
        strategy_id=actual.strategy_id,
        friction_bps=actual.friction_bps,
        parameters=PRIMARY_PARAMETERS[actual.strategy_id],
    )
    expected_signals = result.signals
    expected_fills = result.fills
    signals = tuple(event for event in actual.events if event.event == "signal")
    fills = tuple(event for event in actual.events if event.event == "fill")
    failures: list[str] = []
    label = f"{actual.asset}/{actual.split}/{actual.strategy_id}"
    if actual.returncode != 0 or actual.status != "Completed" or actual.runtime_error:
        failures.append(
            f"{label}: engine status={actual.status}: {actual.runtime_error}"
        )
    if len(signals) != len(expected_signals):
        failures.append(f"{label}/signals: {len(signals)} != {len(expected_signals)}")
    for index, (observed, expected) in enumerate(
        zip(signals, expected_signals, strict=False)
    ):
        if observed.session != expected.decision_session.isoformat():
            failures.append(f"{label}/signals[{index}]/session")
        if observed.action != expected.action or observed.reason != expected.reason:
            failures.append(f"{label}/signals[{index}]/decision")
        if expected.indicator_value is None:
            if observed.indicator is not None:
                failures.append(f"{label}/signals[{index}]/indicator")
        elif (
            observed.indicator is None
            or abs(observed.indicator - expected.indicator_value) > 1e-9
        ):
            failures.append(f"{label}/signals[{index}]/indicator")
    if len(fills) != len(expected_fills):
        failures.append(f"{label}/fills: {len(fills)} != {len(expected_fills)}")
    for index, (observed, expected) in enumerate(
        zip(fills, expected_fills, strict=False)
    ):
        expected_quantity = (
            expected.quantity if expected.side == "entry" else -expected.quantity
        )
        if observed.fill_session != expected.session.isoformat():
            failures.append(f"{label}/fills[{index}]/session")
        if observed.quantity is None or int(observed.quantity) != expected_quantity:
            failures.append(f"{label}/fills[{index}]/quantity")
        if observed.price is None or abs(observed.price - expected.price) > 1e-10:
            failures.append(f"{label}/fills[{index}]/price")
        if observed.reason != expected.reason:
            failures.append(f"{label}/fills[{index}]/reason")
    return failures


def run_battery(
    *,
    project_root: Path,
    snapshot_root: Path,
    artifact_root: Path,
    image: str = DEFAULT_IMAGE,
    limit: int | None = None,
) -> tuple[list[EngineRun], list[str]]:
    """Run the 60 frozen primary configurations and compare event contracts."""

    runs: list[EngineRun] = []
    failures: list[str] = []
    combinations = [
        (asset, split, strategy)
        for asset in ASSETS
        for split in SPLITS
        for strategy in STRATEGIES
    ]
    if limit is not None:
        combinations = combinations[:limit]
    for asset, split, strategy in combinations:
        run = run_one(
            project_root=project_root,
            artifact_root=artifact_root,
            asset=asset,
            split=split,
            strategy_id=strategy,
            image=image,
        )
        runs.append(run)
        failures.extend(_event_mismatch(run, snapshot_root / asset / "normalized.csv"))
    return runs, failures


def _write_report(
    runs: list[EngineRun], failures: list[str], path: Path, image: str
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    failed_labels = {"/".join(failure.split("/")[:3]) for failure in failures}
    payload = {
        "contract": "tradinglab/v0.2-lean-engine-primary/v1",
        "checked": len(runs),
        "passed": len(runs) - len(failed_labels),
        "failed": len(failed_labels),
        "failure_count": len(failures),
        "image": image,
        "failures": failures,
        "runs": [
            {
                **{key: value for key, value in asdict(run).items() if key != "events"},
                "event_count": len(run.events),
            }
            for run in runs
        ],
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="run the V0.2 LEAN primary battery")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).parent)
    parser.add_argument("--snapshot-root", type=Path, required=True)
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("v0_2_lean/output/engine"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("v0_2_lean/output/engine_report.json"),
    )
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    runs, failures = run_battery(
        project_root=args.project_root,
        snapshot_root=args.snapshot_root,
        artifact_root=args.artifact_root,
        image=args.image,
        limit=args.limit,
    )
    _write_report(runs, failures, args.report, args.image)
    failed_labels = {"/".join(failure.split("/")[:3]) for failure in failures}
    print(
        f"checked={len(runs)} passed={len(runs) - len(failed_labels)} "
        f"failed={len(failed_labels)}"
    )
    for failure in failures:
        print(failure)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
