"""Local-only research API for the TradingLAB visualization surface.

The server deliberately exposes no shell, broker, credential, or holdout path.
It is an opt-in convenience layer for running the already-defined historical
Development and Validation batteries from a local browser.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar

from tradinglab.experiments import run_battery

DATASET_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{8,160}$")
ALLOWED_SPLITS = frozenset({"development", "validation_oos"})
MAX_REQUEST_BYTES = 64 * 1024


def dataset_ids(project_root: Path) -> tuple[str, ...]:
    """Return locally materialized dataset identities without reading rows."""

    snapshot_root = project_root / "data" / "snapshots"
    if not snapshot_root.is_dir():
        return ()
    return tuple(
        sorted(
            path.name
            for path in snapshot_root.iterdir()
            if path.is_dir()
            and (path / "manifest.json").is_file()
            and DATASET_ID_PATTERN.fullmatch(path.name)
        )
    )


def validate_battery_request(
    payload: object,
    available_dataset_ids: Sequence[str],
) -> tuple[str, tuple[str, ...]]:
    """Validate the only mutating operation available to the local API."""

    if not isinstance(payload, Mapping):
        raise ValueError("request body must be a JSON object")
    if payload.get("confirmed") is not True:
        raise ValueError("explicit confirmation is required")
    raw_dataset_id = payload.get("dataset_id")
    if not isinstance(raw_dataset_id, str) or not DATASET_ID_PATTERN.fullmatch(
        raw_dataset_id
    ):
        raise ValueError("dataset_id is invalid")
    if raw_dataset_id not in available_dataset_ids:
        raise ValueError("dataset_id is not materialized locally")
    raw_splits = payload.get("splits")
    if not isinstance(raw_splits, list) or not raw_splits:
        raise ValueError("splits must be a non-empty list")
    if any(not isinstance(split, str) for split in raw_splits):
        raise ValueError("splits must contain strings")
    splits = tuple(raw_splits)
    if any(split not in ALLOWED_SPLITS for split in splits):
        raise ValueError("only Development and Validation OOS are available")
    if len(set(splits)) != len(splits):
        raise ValueError("splits must be unique")
    return raw_dataset_id, splits


class DashboardHandler(BaseHTTPRequestHandler):
    """Small JSON API bound to the local research checkout."""

    project_root: ClassVar[Path]

    def _send_json(self, status: int, payload: Mapping[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "http://localhost:3000")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> object:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            content_length = int(raw_length)
        except ValueError as exc:
            raise ValueError("Content-Length is invalid") from exc
        if content_length < 0 or content_length > MAX_REQUEST_BYTES:
            raise ValueError("request body is too large")
        body = self.rfile.read(content_length)
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("request body must be valid JSON") from exc

    def do_OPTIONS(self) -> None:
        self._send_json(204, {})

    def do_GET(self) -> None:
        if self.path == "/api/health":
            ids = dataset_ids(self.project_root)
            self._send_json(
                200,
                {
                    "status": "ok",
                    "research_only": True,
                    "holdout_execution": False,
                    "dataset_ids": ids,
                },
            )
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/api/run-battery":
            self._send_json(404, {"error": "not found"})
            return
        try:
            payload = self._read_json()
            dataset_id, splits = validate_battery_request(
                payload, dataset_ids(self.project_root)
            )
            experiment_id, outcomes, report_dir = run_battery(
                self.project_root,
                dataset_id=dataset_id,
                split_keys=splits,
                confirm_holdout=False,
            )
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        except Exception as exc:  # preserve local failure without leaking a traceback
            self._send_json(500, {"error": f"local research run failed: {exc}"})
            return
        self._send_json(
            200,
            {
                "status": "completed",
                "message": f"{len(outcomes)} trials completed in {experiment_id}",
                "experiment_id": experiment_id,
                "trial_count": len(outcomes),
                "report_dir": str(report_dir.relative_to(self.project_root)),
            },
        )

    def log_message(self, format: str, *args: object) -> None:
        del format, args


def serve(project_root: Path, host: str, port: int) -> None:
    """Serve the local API until interrupted."""

    if (
        not (project_root / ".git").is_dir()
        or not (project_root / "pyproject.toml").is_file()
    ):
        raise ValueError("project root must be the TradingLAB checkout")
    handler = type(
        "TradingLabDashboardHandler",
        (DashboardHandler,),
        {"project_root": project_root},
    )
    server = ThreadingHTTPServer((host, port), handler)
    print(f"TradingLAB local API listening on http://{host}:{port}")
    print("Research-only: broker and Project Holdout execution are unavailable.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description="TradingLAB local dashboard API")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    serve(args.project_root.resolve(), args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
