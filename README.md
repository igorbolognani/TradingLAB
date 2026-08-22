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
uv run tradinglab reproduce --help
```

The generic `run` command cannot access Project Holdout. Non-control trials
must name their exact matching registered Buy & Hold trial. The controlled
holdout command is released only after the same clean experiment contains the
complete ordered Development and Validation OOS batteries; interrupted access
requires the explicit resume flag and never reruns completed configurations.

Generated market snapshots, registry events, trial artifacts, and reports are
kept local by `.gitignore`. Detailed contracts and completion evidence live in
[`docs/MVP_SPEC.md`](docs/MVP_SPEC.md).

Historical performance is research evidence only and does not prove future
profitability, paper-trading readiness, or live-trading suitability.

## Roadmap status after V0.2

The independent V0.2 LEAN reproduction is complete for the frozen primary
battery: 60/60 configurations passed with no signal or fill-contract
divergence. The next roadmap phases are implemented as safe research bridges
in this same repository:

- [`docs/V0_3_V0_5_PLAN.md`](docs/V0_3_V0_5_PLAN.md) is the canonical roadmap and
  decision handoff.
- `v0_3_paper/` contains paper-readiness manifests, a deterministic forward
  simulator, and reconciliation contracts; it has no broker transport.
- `v0_4_tradingview/` contains a Pine v6 confirmed-bar observer and a local
  alert parser; TradingView is not canonical.
- `v0_5_forex/` contains an offline UTC EURUSD daily-bar contract, replay, and an
  indicator-only MT5 observer; it is separate from the XNYS ETF registry.
- `v0_6_portfolio/` contains a shared-cash portfolio reference replay with
  equal-weight and inverse-volatility baselines; it does not optimize or trade.

An actual Alpaca account, MT5 terminal, external alert delivery, or order
submission remains a human-gated future integration and is intentionally absent
from the repository.

## Research Control Room

The `site/` directory contains the interface source for the private Sites
surface. It is intentionally empty until a real local report is imported; it
does not ship Yahoo rows or synthetic performance values. For local use:

```bash
cd site && npm install && npm run dev
# in another terminal, from the repository root:
uv run tradinglab-dashboard
```

The browser can load an `all_trials.csv`/JSON export and, when the local API is
running, request a Development or Validation battery. Project Holdout,
broker execution, paper trading, and live trading remain blocked. The GitHub
handoff is documented in [`docs/GITHUB_MIGRATION.md`](docs/GITHUB_MIGRATION.md).

### Candles e qualidade de dados

Na tela **Market data**, o servidor local pode devolver candles OHLCV reais do
snapshot validado, junto com provedor, versão, horários, basis de preço,
checksum, ações corporativas, indicadores SMA/ATR e diagnóstico de qualidade:

```text
GET /api/health
GET /api/datasets
GET /api/candles?dataset_id=<id>&symbol=SPY&limit=240
```

O endpoint identifica explicitamente o modo como `historical_snapshot` e
`realtime_active=false`. Ele não promete baixa latência enquanto o projeto não
tiver um fornecedor licenciado com feed ao vivo. A matriz de fornecedores,
licenciamento, timestamps, alternativas BYOD e gates de segurança está em
[`docs/DATA_PROVIDER_RESEARCH.md`](docs/DATA_PROVIDER_RESEARCH.md).
