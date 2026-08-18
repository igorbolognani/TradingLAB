"""Immutable dataset snapshots, manifests, checksums, loading, and validation."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from tradinglab.calendar import regular_sessions
from tradinglab.constants import (
    EXCHANGE_CALENDAR,
    NORMALIZATION_FORMULA,
    NORMALIZATION_VERSION,
    PRICE_BASIS_ID,
    TIMEZONE,
)
from tradinglab.data.normalization import (
    dataframe_csv_bytes,
    normalize_provider_frame,
)
from tradinglab.data_source import ProviderFrame, RetrievalRequest, YFinanceSource
from tradinglab.hashing import canonical_json_bytes, sha256_bytes, sha256_file


class DataSource(Protocol):
    def fetch(self, symbol: str, request: RetrievalRequest) -> ProviderFrame: ...


class SnapshotStore:
    """Own local immutable market snapshots; never overwrite an identity."""

    def __init__(self, root: Path, source: DataSource | None = None) -> None:
        self.root = root
        self.source = source or YFinanceSource()

    def fetch_dataset(self, request: RetrievalRequest) -> dict[str, Any]:
        """Fetch, normalize, validate, hash, and atomically identify one refresh."""

        retrieved_at = datetime.now(UTC).isoformat(timespec="microseconds")
        serialized: dict[str, dict[str, bytes]] = {}
        providers: dict[str, ProviderFrame] = {}
        normalized_by_symbol: dict[str, Any] = {}
        for symbol in request.symbols:
            provider = self.source.fetch(symbol, request)
            frames = normalize_provider_frame(
                provider,
                requested_start=request.start,
                requested_end_exclusive=request.end_exclusive,
            )
            providers[symbol] = provider
            normalized_by_symbol[symbol] = frames
            serialized[symbol] = {
                "raw": dataframe_csv_bytes(frames.raw, index_label="ProviderIndex"),
                "actions": dataframe_csv_bytes(
                    frames.actions, index_label="ProviderIndex"
                ),
                "normalized": dataframe_csv_bytes(
                    frames.normalized, index_label="Session"
                ),
            }

        content_checksums = {
            symbol: {
                layer: sha256_bytes(content)
                for layer, content in sorted(layers.items())
            }
            for symbol, layers in sorted(serialized.items())
        }
        identity_payload = {
            "retrieved_at": retrieved_at,
            "symbols": request.symbols,
            "requested_start": request.start.isoformat(),
            "requested_end_exclusive": request.end_exclusive.isoformat(),
            "checksums": content_checksums,
        }
        stamp = datetime.fromisoformat(retrieved_at).strftime("%Y%m%dT%H%M%S%fZ")
        dataset_id = (
            f"ds_{stamp}_{sha256_bytes(canonical_json_bytes(identity_payload))[:12]}"
        )
        dataset_dir = self.root / dataset_id
        dataset_dir.mkdir(parents=True, exist_ok=False)

        file_paths: dict[str, dict[str, str]] = {}
        for symbol, layers in sorted(serialized.items()):
            symbol_dir = dataset_dir / symbol
            symbol_dir.mkdir()
            file_paths[symbol] = {}
            for layer, content in sorted(layers.items()):
                relative_path = f"{symbol}/{layer}.csv"
                (dataset_dir / relative_path).write_bytes(content)
                file_paths[symbol][layer] = relative_path

        first_sessions = {
            symbol: frames.normalized.index.min().date().isoformat()
            for symbol, frames in normalized_by_symbol.items()
        }
        last_sessions = {
            symbol: frames.normalized.index.max().date().isoformat()
            for symbol, frames in normalized_by_symbol.items()
        }
        row_counts = {
            symbol: {
                "raw": len(frames.raw),
                "actions": len(frames.actions),
                "normalized": len(frames.normalized),
            }
            for symbol, frames in normalized_by_symbol.items()
        }
        dataset_checksum = sha256_bytes(canonical_json_bytes(content_checksums))
        representative = providers[request.symbols[0]]
        manifest: dict[str, Any] = {
            "dataset_id": dataset_id,
            "dataset_checksum": dataset_checksum,
            "symbols": list(request.symbols),
            "provider": representative.provider,
            "provider_version": representative.provider_version,
            "retrieved_at": retrieved_at,
            "requested_start": request.start.isoformat(),
            "requested_end_exclusive": request.end_exclusive.isoformat(),
            "effective_first_session": first_sessions,
            "effective_last_session": last_sessions,
            "interval": "1d",
            "source_timezone": {
                symbol: frames.source_timezone
                for symbol, frames in normalized_by_symbol.items()
            },
            "normalized_timezone": TIMEZONE,
            "exchange_calendar": EXCHANGE_CALENDAR,
            "calendar_configuration": {
                "name": EXCHANGE_CALENDAR,
                "start": request.start.isoformat(),
                "end": request.end_exclusive.isoformat(),
                "side": "both",
                "bounds_padding_calendar_days": 7,
                "session_range_end_semantics": (
                    "inclusive then filter exclusive request end"
                ),
            },
            "exact_query_arguments": representative.exact_query_arguments,
            "raw_schema": {
                symbol: [str(column) for column in frames.raw.columns]
                for symbol, frames in normalized_by_symbol.items()
            },
            "normalized_schema": [
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
                "AdjustmentFactor",
            ],
            "price_basis_id": PRICE_BASIS_ID,
            "normalization_version": NORMALIZATION_VERSION,
            "normalization_formula": NORMALIZATION_FORMULA,
            "row_counts": row_counts,
            "missing_values": {
                symbol: frames.missing_values
                for symbol, frames in normalized_by_symbol.items()
            },
            "missing_session_diagnostics": {
                symbol: frames.missing_session_diagnostics
                for symbol, frames in normalized_by_symbol.items()
            },
            "file_paths": file_paths,
            "checksums": content_checksums,
            "completed_regular_sessions_only": True,
            "forward_fill_applied": False,
            "raw_rows_redistributable": False,
        }
        (dataset_dir / "manifest.json").write_bytes(canonical_json_bytes(manifest))
        self.validate_dataset(dataset_id)
        return manifest

    def manifest_path(self, dataset_id: str) -> Path:
        return self.root / dataset_id / "manifest.json"

    def load_manifest(self, dataset_id: str) -> dict[str, Any]:
        path = self.manifest_path(dataset_id)
        if not path.is_file():
            raise FileNotFoundError(f"unknown dataset_id: {dataset_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("dataset_id") != dataset_id:
            raise ValueError("dataset manifest identity mismatch")
        return payload

    def load_normalized(self, dataset_id: str, symbol: str) -> pd.DataFrame:
        manifest = self.load_manifest(dataset_id)
        if symbol not in manifest["symbols"]:
            raise ValueError(f"{symbol} is not part of {dataset_id}")
        relative = manifest["file_paths"][symbol]["normalized"]
        path = self.root / dataset_id / relative
        expected_hash = manifest["checksums"][symbol]["normalized"]
        if sha256_file(path) != expected_hash:
            raise ValueError(f"normalized snapshot checksum mismatch: {path}")
        frame = pd.read_csv(path, parse_dates=["Session"], index_col="Session")
        parsed = pd.DatetimeIndex(frame.index)
        if parsed.tz is None:
            parsed = parsed.tz_localize(ZoneInfo(TIMEZONE))
        else:
            parsed = parsed.tz_convert(ZoneInfo(TIMEZONE))
        frame.index = pd.DatetimeIndex(parsed, name="Session")
        return frame

    def validate_dataset(self, dataset_id: str) -> dict[str, Any]:
        """Recheck identity, checksums, row/range contracts, and reconciliation."""

        manifest = self.load_manifest(dataset_id)
        required = {
            "dataset_id",
            "dataset_checksum",
            "symbols",
            "provider",
            "provider_version",
            "retrieved_at",
            "requested_start",
            "requested_end_exclusive",
            "effective_first_session",
            "effective_last_session",
            "interval",
            "source_timezone",
            "normalized_timezone",
            "exchange_calendar",
            "calendar_configuration",
            "exact_query_arguments",
            "raw_schema",
            "normalized_schema",
            "price_basis_id",
            "normalization_version",
            "normalization_formula",
            "row_counts",
            "missing_values",
            "missing_session_diagnostics",
            "file_paths",
            "checksums",
        }
        missing = sorted(required.difference(manifest))
        if missing:
            raise ValueError(f"dataset manifest missing fields: {missing}")
        if manifest["requested_end_exclusive"] > "2026-01-01":
            raise ValueError("dataset request exceeds the V0.1 date boundary")

        actual_checksums: dict[str, dict[str, str]] = {}
        for symbol in manifest["symbols"]:
            actual_checksums[symbol] = {}
            for layer in ("raw", "actions", "normalized"):
                path = self.root / dataset_id / manifest["file_paths"][symbol][layer]
                actual = sha256_file(path)
                expected = manifest["checksums"][symbol][layer]
                if actual != expected:
                    raise ValueError(f"checksum mismatch for {symbol}/{layer}")
                actual_checksums[symbol][layer] = actual
            normalized = self.load_normalized(dataset_id, symbol)
            if (
                normalized.index.has_duplicates
                or not normalized.index.is_monotonic_increasing
            ):
                raise ValueError(f"invalid normalized index for {symbol}")
            if normalized.index.max().year >= 2026:
                raise ValueError(f"2026 row accepted for {symbol}")
            if len(normalized) != manifest["row_counts"][symbol]["normalized"]:
                raise ValueError(f"row count mismatch for {symbol}")
            required = {"Open", "High", "Low", "Close", "Volume", "AdjustmentFactor"}
            if not required.issubset(normalized.columns):
                raise ValueError(f"normalized schema mismatch for {symbol}")
            if normalized[list(required)].isna().any().any():
                raise ValueError(f"normalized required values are missing for {symbol}")
            if (normalized[["Open", "High", "Low", "Close"]] <= 0).any().any():
                raise ValueError(f"normalized price is nonpositive for {symbol}")
            if (normalized["Volume"] < 0).any():
                raise ValueError(f"negative volume for {symbol}")
            expected_sessions = regular_sessions(
                normalized.index.min().date(), normalized.index.max().date()
            )
            if len(normalized.index.difference(expected_sessions)):
                raise ValueError(f"non-XNYS session accepted for {symbol}")

            raw_path = self.root / dataset_id / manifest["file_paths"][symbol]["raw"]
            action_path = (
                self.root / dataset_id / manifest["file_paths"][symbol]["actions"]
            )
            raw = pd.read_csv(raw_path, index_col="ProviderIndex")
            actions = pd.read_csv(action_path, index_col="ProviderIndex")
            raw_index = pd.to_datetime(raw.index, utc=True).tz_convert(
                ZoneInfo(TIMEZONE)
            )
            raw.index = pd.DatetimeIndex(raw_index, name="ProviderIndex")
            action_index = pd.to_datetime(actions.index, utc=True).tz_convert(
                ZoneInfo(TIMEZONE)
            )
            actions.index = pd.DatetimeIndex(action_index, name="ProviderIndex")
            normalized_dates = pd.DatetimeIndex(
                [
                    pd.Timestamp(value.date(), tz=ZoneInfo(TIMEZONE))
                    for value in raw.index
                ],
                name="Session",
            )
            factor = raw["Adj Close"].astype(float) / raw["Close"].astype(float)
            if not np.allclose(
                factor.to_numpy(),
                normalized["AdjustmentFactor"].to_numpy(),
                rtol=1e-12,
                atol=1e-12,
            ):
                raise ValueError(f"adjustment factor mismatch for {symbol}")
            if not normalized.index.equals(normalized_dates):
                raise ValueError(f"raw/normalized session mismatch for {symbol}")
            for column in ("Open", "High", "Low", "Close"):
                expected_values = (
                    raw[column].astype(float).to_numpy() * factor.to_numpy()
                )
                if not np.allclose(
                    expected_values,
                    normalized[column].to_numpy(),
                    rtol=1e-12,
                    atol=1e-10,
                ):
                    raise ValueError(f"raw/normalized {column} mismatch for {symbol}")
            for column in ("Dividends", "Stock Splits", "Capital Gains"):
                raw_values = (
                    raw[column].astype(float).to_numpy()
                    if column in raw.columns
                    else np.zeros(len(raw))
                )
                if not np.allclose(
                    raw_values,
                    actions[column].astype(float).to_numpy(),
                    rtol=0,
                    atol=0,
                ):
                    raise ValueError(f"corporate action mismatch for {symbol}/{column}")
        actual_dataset_checksum = sha256_bytes(canonical_json_bytes(actual_checksums))
        if actual_dataset_checksum != manifest["dataset_checksum"]:
            raise ValueError("dataset checksum mismatch")
        return {
            "dataset_id": dataset_id,
            "dataset_checksum": actual_dataset_checksum,
            "valid": True,
            "validated_at": (datetime.now(UTC) + timedelta(0)).isoformat(),
        }
