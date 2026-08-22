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
from urllib.parse import parse_qs, urlparse

from tradinglab.calendar import regular_sessions
from tradinglab.data import (
    SnapshotStore,
    calculate_candle_summary,
    inspect_candles,
    serialize_candles,
)
from tradinglab.experiments import run_battery

DATASET_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{8,160}$")
SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,24}$")
ALLOWED_SPLITS = frozenset({"development", "validation_oos"})
MAX_REQUEST_BYTES = 64 * 1024
MAX_CANDLE_ROWS = 1_000
ALLOWED_BROWSER_ORIGINS = frozenset(
    {
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://tradinglab-research-lab.igorbolognani768385.chatgpt.site",
    }
)


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


def dataset_catalog(project_root: Path) -> list[dict[str, Any]]:
    """Return provenance-only dataset summaries, never market rows."""

    store = SnapshotStore(project_root / "data" / "snapshots")
    catalog: list[dict[str, Any]] = []
    for dataset_id in dataset_ids(project_root):
        manifest = store.load_manifest(dataset_id)
        catalog.append(
            {
                "dataset_id": dataset_id,
                "dataset_checksum": manifest.get("dataset_checksum"),
                "manifest_hash": manifest.get("manifest_hash"),
                "provider": manifest.get("provider"),
                "provider_version": manifest.get("provider_version"),
                "retrieved_at": manifest.get("retrieved_at"),
                "requested_start": manifest.get("requested_start"),
                "requested_end_exclusive": manifest.get("requested_end_exclusive"),
                "symbols": manifest.get("symbols", []),
                "interval": manifest.get("interval"),
                "normalized_timezone": manifest.get("normalized_timezone"),
                "exchange_calendar": manifest.get("exchange_calendar"),
                "price_basis_id": manifest.get("price_basis_id"),
                "completed_regular_sessions_only": manifest.get(
                    "completed_regular_sessions_only", False
                ),
            }
        )
    return catalog


def recommended_dataset_id(project_root: Path) -> str | None:
    """Choose the newest snapshot whose complete integrity contract passes."""

    store = SnapshotStore(project_root / "data" / "snapshots")
    for dataset_id in reversed(dataset_ids(project_root)):
        try:
            store.validate_dataset(dataset_id)
        except (OSError, ValueError):
            continue
        return dataset_id
    return None


def candle_payload(
    project_root: Path,
    *,
    dataset_id: str,
    symbol: str,
    limit: int,
) -> dict[str, Any]:
    """Load real local candles and attach integrity, source, and calculations."""

    if not DATASET_ID_PATTERN.fullmatch(dataset_id):
        raise ValueError("dataset_id is invalid")
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise ValueError("symbol is invalid")
    if limit < 1 or limit > MAX_CANDLE_ROWS:
        raise ValueError(f"limit must be between 1 and {MAX_CANDLE_ROWS}")

    store = SnapshotStore(project_root / "data" / "snapshots")
    manifest = store.load_manifest(dataset_id)
    if symbol not in manifest.get("symbols", []):
        raise ValueError(f"{symbol} is not part of {dataset_id}")
    # This verifies the complete manifest and normalized snapshot before any
    # row is returned. It is intentionally explicit for a local research API.
    validation = store.validate_dataset(dataset_id)
    frame = store.load_normalized(dataset_id, symbol)
    selected = frame.tail(limit)
    expected = regular_sessions(frame.index.min().date(), frame.index.max().date())
    quality = inspect_candles(frame, expected_sessions=expected)
    quality["manifest_validation"] = validation
    return {
        "symbol": symbol,
        "timeframe": manifest.get("interval", "1d"),
        "candles": serialize_candles(frame, limit=limit),
        "returned_row_count": len(selected),
        "available_row_count": len(frame),
        "source": {
            "provider": manifest.get("provider"),
            "provider_version": manifest.get("provider_version"),
            "retrieved_at": manifest.get("retrieved_at"),
            "exact_query_arguments": manifest.get("exact_query_arguments", {}),
            "dataset_id": dataset_id,
            "dataset_checksum": manifest.get("dataset_checksum"),
            "manifest_hash": manifest.get("manifest_hash"),
            "exchange_calendar": manifest.get("exchange_calendar"),
            "source_timezone": manifest.get("source_timezone", {}).get(symbol),
            "normalized_timezone": manifest.get("normalized_timezone"),
            "price_basis_id": manifest.get("price_basis_id"),
            "normalization_version": manifest.get("normalization_version"),
            "corporate_actions_preserved": True,
            "raw_rows_redistributable": manifest.get("raw_rows_redistributable", False),
        },
        "freshness": {
            "mode": "historical_snapshot",
            "last_event_time": quality.get("last_event_time"),
            "last_session": frame.index.max().date().isoformat(),
            "bar_is_complete": bool(
                manifest.get("completed_regular_sessions_only", False)
            ),
            "realtime_active": False,
            "latency_ms": None,
            "message": (
                "Este endpoint serve um snapshot histórico local; "
                "não é feed em tempo real."
            ),
        },
        "quality": quality,
        "calculated": calculate_candle_summary(frame),
    }


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
        origin = self.headers.get("Origin")
        if origin in ALLOWED_BROWSER_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
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
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            ids = dataset_ids(self.project_root)
            self._send_json(
                200,
                {
                    "status": "ok",
                    "research_only": True,
                    "holdout_execution": False,
                    "dataset_ids": ids,
                    "recommended_dataset_id": recommended_dataset_id(self.project_root),
                },
            )
            return
        if parsed.path == "/api/datasets":
            try:
                self._send_json(200, {"datasets": dataset_catalog(self.project_root)})
            except (OSError, ValueError) as exc:
                self._send_json(500, {"error": f"dataset catalog failed: {exc}"})
            return
        if parsed.path == "/api/candles":
            query = parse_qs(parsed.query, keep_blank_values=True)
            dataset_id = query.get("dataset_id", [""])[0]
            symbol = query.get("symbol", [""])[0].upper()
            raw_limit = query.get("limit", ["240"])[0]
            try:
                limit = int(raw_limit)
                payload = candle_payload(
                    self.project_root,
                    dataset_id=dataset_id,
                    symbol=symbol,
                    limit=limit,
                )
            except (OSError, ValueError) as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, payload)
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
