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

## D-006 — External phases remain transport-free until a human gate

**Status:** accepted for V0.3–V0.5.

V0.3 implements paper-readiness manifests, deterministic forward simulation,
and fill reconciliation, but no Alpaca SDK, credential, endpoint, or order
submission. V0.4 implements a confirmed-bar TradingView observer and a local
payload parser. V0.5 implements an offline UTC Forex contract and replay plus
an indicator-only MT5 observer. These phases complement V0.1/V0.2 while keeping
external side effects absent from the research repository.

## D-007 — Future Alpaca opening semantics are MOO/OPG by default

**Status:** accepted as a deferred design default.

The V0.1 decision-to-next-open contract maps most directly to a future equity
market-on-open order using Alpaca's `opg` time-in-force. A limit-on-open order
requires a separately specified limit policy. No adapter is implemented until
there is an explicit operational and safety approval; paper fills remain
non-equivalent to the normalized total-return backtest.

## D-008 — Forex is a separate research domain

**Status:** accepted for V0.5.

The first Forex pilot uses EURUSD daily bars with explicit UTC timestamps and
an offline import. It does not assume XNYS sessions, dividend treatment,
equity sizing, or broker execution semantics transfer unchanged. Forex results
are kept outside the V0.1 ETF registry and require separate broker/session/data
provenance before any MT5 Strategy Tester comparison.

## D-009 — V0.6 portfolio reference before acceleration

**Status:** accepted and implemented for V0.6.

The portfolio layer begins with a small independent reference replay using
shared cash, aligned sessions, integer long-only positions, explicit
sell-before-buy rebalances, equal-weight and inverse-volatility baselines. It
now runs against the validated five-ETF snapshot through the local CLI, API and
private interface for Development or Validation OOS. It does not add automatic
optimization, access the Project Holdout, or make VectorBT authoritative. Any
future accelerator must reproduce this contract before it is used for scale.
