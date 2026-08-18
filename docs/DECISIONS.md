# Decisions

## D-001 — Canonical accounting inside the Backtesting.py adapter

**Status:** accepted for V0.1.

Backtesting.py is invoked behind `BacktestingPyAdapter` with every execution
option explicit. A deterministic canonical ledger inside the same adapter is
authoritative because the V0.1 quantity-at-fill formula, exact all-in friction,
split-boundary reset, and terminally open lifecycle contract must not depend on
engine display statistics or hidden defaults. An engine reference replay is
extracted for semantic diagnostics; strategies and metrics remain independent.

## D-002 — Immutable local storage

**Status:** accepted for V0.1.

CSV snapshots and JSON manifests use stable columns/order and SHA-256 hashes.
Dataset identities include retrieval identity so a refresh cannot overwrite an
earlier snapshot. Trial identifiers are unique and directories are created
exclusively. Market rows and generated results remain ignored local artifacts;
source-controlled synthetic fixtures remain visible.

## D-003 — Dependency and command tooling

**Status:** accepted for V0.1.

Python 3.12 and uv provide an isolated `.venv`, a lockfile, and one module/CLI
entry point. pytest, Ruff, and mypy are the minimum test/format/lint/type-check
tooling for this new repository.

