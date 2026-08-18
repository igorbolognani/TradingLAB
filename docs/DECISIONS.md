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

## D-004 — Holdout access is a central capability, not a CLI convention

**Status:** accepted for V0.1.

`ExperimentRunner` refuses a Project Holdout trial unless `run_battery` has
issued an internal permit after verifying the exact ordered Development and
Validation OOS batteries under one clean immutable fingerprint. The first
authorized access is append-only and global. A resume is explicit, fingerprint
locked, and skips already-completed configurations while retaining failed or
interrupted attempts.

## D-005 — Analytical equivalence and full reproduction are distinct

**Status:** accepted for V0.1.

The four canonical analytical CSVs retain a stable content hash. A positive
full reproduction additionally requires the recorded commit/branch and clean
state, Python and dependency lock, engine version, current spec hash,
authenticated dataset identity and metadata, registered benchmark provenance,
and intact checksummed artifacts. Reports and plots are evidence artifacts even
though they do not change the analytical hash.
