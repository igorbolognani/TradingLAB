"""Append-only JSONL trial event registry and source provenance."""

import json
import os
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from tradinglab.hashing import canonical_json_bytes, lock_hash

EventType = Literal["started", "completed", "failed", "holdout_seen"]


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _git(project_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def code_provenance(project_root: Path) -> dict[str, Any]:
    """Capture commit plus exact dirty paths without staging or mutation."""

    porcelain = _git(project_root, "status", "--porcelain=v1")
    dirty_paths = [line[3:] for line in porcelain.splitlines() if len(line) >= 4]
    return {
        "git_commit": _git(project_root, "rev-parse", "HEAD"),
        "git_branch": _git(project_root, "branch", "--show-current"),
        "dirty_worktree": bool(porcelain),
        "dirty_paths": dirty_paths,
        "python_version": platform.python_version(),
        "dependency_lock_hash": lock_hash(project_root),
    }


class TrialRegistry:
    """Write each lifecycle fact as a new durable line; never mutate history."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, event: dict[str, Any]) -> None:
        event_type = event.get("event_type")
        if event_type not in {"started", "completed", "failed", "holdout_seen"}:
            raise ValueError(f"unsupported registry event: {event_type}")
        if "created_at" not in event:
            raise ValueError("registry events require created_at")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = canonical_json_bytes(event)
        descriptor = os.open(
            self.path,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o600,
        )
        try:
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        result: list[dict[str, Any]] = []
        with self.path.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, start=1):
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"invalid registry JSONL at line {number}"
                    ) from exc
                if not isinstance(payload, dict):
                    raise ValueError(f"registry line {number} is not an object")
                result.append(payload)
        return result

    def events_for_trial(self, trial_id: str) -> list[dict[str, Any]]:
        return [event for event in self.events() if event.get("trial_id") == trial_id]

    def completed_for_experiment(self, experiment_id: str) -> list[dict[str, Any]]:
        return [
            event
            for event in self.events()
            if event.get("experiment_id") == experiment_id
            and event.get("event_type") == "completed"
        ]

    def holdout_seen(self) -> bool:
        return any(
            event.get("event_type") == "holdout_seen"
            or (
                event.get("event_type") == "completed"
                and event.get("temporal_split") == "project_holdout"
            )
            for event in self.events()
        )
