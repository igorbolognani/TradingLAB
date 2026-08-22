# TradingLAB V0.2 — independent LEAN reproduction

V0.2 is a second implementation of the frozen V0.1 research contract in
QuantConnect LEAN. It lives in this repository so specifications, local
snapshots and comparison evidence remain together, but it does not import the
V0.1 `tradinglab` package or use Backtesting.py accounting.

The six acceptance dimensions are:

1. CASH and Buy & Hold controls;
2. Trend SMA200;
3. Mean Reversion Z20;
4. SPY, IWM, EFA, TLT and GLD across Development, Validation OOS and Project
   Holdout;
5. causal close decision, next-open order eligibility, integer sizing, one-side
   friction and canonical terminal valuation;
6. comparison of the independent output against the frozen V0.1 primary
   artifacts using explicit tolerances.

## Offline comparison

The independent replay and comparison do not require network access or Docker:

```bash
MPLCONFIGDIR=/tmp/tradinglab-mpl \
UV_CACHE_DIR=/tmp/tradinglab-uv-cache \
uv run python -m v0_2_lean.validation \
  --snapshot-root data/snapshots/ds_20260818T142727647796Z_48e34b6b3110 \
  --report-csv artifacts/reports/report_exp_20260818T142752Z_33c6743bb4_578f8acf6533/all_trials.csv
```

The command checks all 60 primary configurations.  V0.2 does not rerun or
modify the V0.1 holdout registry.

## LEAN local run

The local CLI was installed as `lean==1.0.228` through `uvx`. Keep it
isolated from the V0.1 environment; the root project intentionally does not
declare a LEAN dependency.

Prepare only the normalized local input:

```bash
uv run python -m v0_2_lean.prepare_data \
  --snapshot-root data/snapshots/ds_20260818T142727647796Z_48e34b6b3110 \
  --output-root v0_2_lean/lean_data
```

The actual engine run requires the QuantConnect LEAN CLI and Docker. A LEAN
invocation is evidence only when its engine output is captured and compared;
the offline replay is not presented as a substitute for a LEAN run.

After Docker has the official image available, run from this directory:

```bash
uvx --from lean==1.0.228 lean backtest . \
  --no-update --image quantconnect/lean:17998 \
  --lean-config lean.json \
  --output output/backtest \
  --parameter asset SPY \
  --parameter split project_holdout \
  --parameter strategy_id CASH_0_V1 \
  --parameter friction_bps 5
```

The pinned image is `quantconnect/lean:17998`. Its download is an
environment prerequisite and is not represented as a successful engine
validation until the command above completes and its output is reviewed.

For the complete primary engine gate, use the isolated runner.  It executes
the 60 frozen configurations one at a time in clean `/tmp` staging copies and
compares LEAN signal/fill events with the independent replay:

```bash
uv run python -m v0_2_lean.engine_runner \
  --snapshot-root data/snapshots/ds_20260818T142727647796Z_48e34b6b3110 \
  --artifact-root v0_2_lean/output/engine \
  --report v0_2_lean/output/engine_report.json
```

The runner preserves local engine outputs under the ignored output directory.
LEAN may leave root-owned Python cache files in its temporary staging copy;
these are outside the repository and are not research data.

The smoke validation and the complete primary battery use the pinned image
`quantconnect/lean:17998` with digest
`sha256:c76cf4f7bc88f16986a671c27e8107a2f9606eb5a67c8ac817a04f76feb5502f`.
All 60 primary configurations completed and matched the independent replay's
signal/fill contract.  This is an execution equivalence result, not a
strategy-promotion or future-performance result.

No broker, paper/live, optimization or order-submission capability is part of
V0.2. `MarketOnOpenOrder` is used only as a historical next-open simulation.

Research-only candidates are intentionally separate from this primary gate.
Run their fixed offline battery with:

```bash
uv run python -c \
  'from pathlib import Path; from v0_2_lean.research_candidates import run_candidate_battery; print(run_candidate_battery(Path("data/snapshots/ds_20260818T142727647796Z_48e34b6b3110"), Path("v0_2_lean/output/research_candidates.csv")))'
```
