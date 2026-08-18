# TradingLAB V0.1

TradingLAB is a small, auditable, reproducible local laboratory for causal
daily-bar quantitative research. It formalizes four fixed controls/strategies,
preserves immutable market-data snapshots and trial artifacts, and evaluates
predeclared temporal, cross-asset, parameter, and execution-friction tests.

It is not a trading bot, recommendation system, broker integration, paper
trader, machine-learning system, or production platform.

## Safety boundary

```text
LIVE TRADING = IMPOSSIBLE
REAL MONEY = 0
BROKER ORDER SUBMISSION = ABSENT
```

The strongest guarantee is structural: **broker execution code does not
exist**. No broker SDK, client, credential handling, paper/live environment, or
order-submission network path belongs in V0.1.

## Core contract

```text
confirmed XNYS close t
-> causal engine-independent decision
-> eligible next valid XNYS open
-> integer long/cash execution on normalized prices
-> canonical gross/net ledgers and metrics
-> immutable local artifacts and append-only events
```

The four canonical specifications are `CASH_0_V1`, `BUY_HOLD_V1`,
`TREND_SMA200_V1`, and `MEANREV_Z20_V1`. Each run is one independent asset
experiment; no multiasset portfolio is constructed.

## Data and licensing boundaries

yfinance/Yahoo market data is used only for V0.1 personal
educational/research purposes. Do not redistribute downloaded Yahoo market
datasets as third-party project deliverables. The replaceability boundary is
the normalized internal data contract; yfinance is isolated in one source
module. Do not rely on implicit yfinance defaults for data semantics.

Backtesting.py AGPL-3.0 is accepted for V0.1 private/local research. V0.1 is not
intended for distribution, SaaS deployment, proprietary product integration,
or commercial offering. Before any future distribution, hosted service, or
commercial transition, review the engine dependency and license architecture
separately.

The normalized split- and dividend-adjusted open is a research execution proxy,
not a claim about an actual broker fill.

## Setup and commands

The exact dependency versions are recorded in `uv.lock`.

```bash
uv sync --all-groups
uv run tradinglab --help
uv run tradinglab fetch --help
uv run tradinglab validate-dataset --help
uv run tradinglab run --help
uv run tradinglab run-battery --help
uv run tradinglab report --help
uv run tradinglab registry --help
```

Generated market snapshots, registry events, trial artifacts, and reports are
kept local by `.gitignore`. Detailed contracts and completion evidence live in
[`docs/MVP_SPEC.md`](docs/MVP_SPEC.md).

Historical performance is research evidence only and does not prove future
profitability, paper-trading readiness, or live-trading suitability.

