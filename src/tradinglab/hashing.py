"""Deterministic serialization and SHA-256 helpers."""

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON-compatible data deterministically and reject NaN/Infinity."""

    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode()


def sha256_bytes(value: bytes) -> str:
    """Return a lowercase SHA-256 hex digest."""

    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    """Hash a file without loading the entire artifact in memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def lock_hash(project_root: Path) -> str:
    """Hash the uv lockfile that fixes the dependency environment."""

    return sha256_file(project_root / "uv.lock")
