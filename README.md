# TradingLAB

TradingLAB is a research-first quantitative trading workspace. Its canonical
Python laboratory remains local, reproducible and independent of brokers. The
same repository now includes a separately gated owner-only Alpaca Paper
monitor for real quotes, candles, account state, positions and orders. Live
trading, custody, deposits, payments and automatic strategy promotion are not
implemented.

The public web surface is a concise presentation landing page plus an
**About & Usage** guide. After authentication, the application opens a compact
trading workspace with separate **Workspace**, **Research** and **Manage**
navigation. Owner-only market, portfolio and administration tools remain
hidden from invited users; **Data & trust** gives all authenticated users a
small, readable view of source and quality. The Paper bridge keeps credentials
on the server and defaults to read-only monitoring; new Paper orders require
explicit safety flags and a kill-switch release.

The current integration boundary is documented in
[`docs/ALPACA_PAPER_BRIDGE.md`](docs/ALPACA_PAPER_BRIDGE.md). Direct
credentials are never committed or sent to browser clients.

Historical V0.1 research details follow.

TradingLAB is a small, auditable, reproducible local laboratory for causal
daily-bar quantitative research. It formalizes four fixed controls/strategies,
preserves immutable market-data snapshots and trial artifacts, and evaluates
predeclared temporal, cross-asset, parameter, and execution-friction tests.

The research core is not a trading bot, recommendation system, or live
trading platform. The optional Paper monitor is an integration surface for
owner-controlled testing, not evidence of profitability or readiness for real
capital.

## Safety boundary

```text
LIVE TRADING = ABSENT
REAL MONEY = 0
PAPER ORDER SUBMISSION = DISABLED BY DEFAULT
```

The research core has no broker dependency. The separate Paper bridge uses
server-side direct API calls, is owner-gated, forces the Paper/IEX domains, and
has no live path.

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

O aplicativo base não importa yfinance. Para habilitar somente no seu
computador o conector privado yfinance/Yahoo usado pelo V0.1:

```bash
uv sync --all-groups --extra yahoo
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
- `v0_6_portfolio/` contains a shared-cash portfolio replay with equal-weight
  and inverse-volatility baselines; the local API and CLI run it against the
  validated five-ETF snapshot for Development or Validation OOS. It does not
  optimize, access the Project Holdout, or trade.

The owner-only Alpaca Paper monitor is now a bounded integration. MT5,
external alert delivery, live trading, custody, payments and production
capital remain outside the product.

## V1.0 research operational

V1.0 adds a provider-neutral candle contract alongside the private yfinance
snapshot. A licensed export or BYOD CSV can be validated and displayed without
using Yahoo or network access:

```bash
uv run tradinglab validate-candle-file \
  --path /path/to/licensed-candles.csv \
  --symbol SPY

uv run tradinglab-dashboard \
  --candle-file /path/to/licensed-candles.csv
```

The interface also imports the same CSV in the browser without uploading it.
It reports source, provider version, event/receive timestamps, data age,
completeness and measured latency scope. Realtime remains explicitly
`realtime_active=false` until a licensed live adapter is selected and verified.
The complete V1.0 contract and later gates are in
[`docs/V1_0_SPEC.md`](docs/V1_0_SPEC.md).

## Research Control Room

The `site/` directory contains two deliberately separate surfaces: a public
landing page for presentation and an authenticated application for use. The
landing page has no application sidebar and explains the product through a
short visual flow and interactive preview. The detailed product, usage,
metrics, asset and support guide lives in **About & Usage**, available before
and after login. After login,
the application opens the dashboard and groups its tools into **Workspace**
(dashboard, Paper, private market data and portfolio replay), **Research**
(owner experiments plus the public-facing Data & trust summary) and **Manage**
(About & Usage, profile, settings, help and owner-only Admin/use tips). The owner gate hides
Market data, Portfolio, Experiments and Admin from other accounts. It is
intentionally empty until a real local report is imported; it does not ship
Yahoo rows or synthetic performance values. For local use:

```bash
cd site && npm install && npm run dev
# in another terminal, from the repository root:
uv run tradinglab-dashboard
```

The browser can load an `all_trials.csv`/JSON export and, when the local API is
running, request a Development or Validation battery. Project Holdout and the
research-to-order path remain blocked. The separately gated Paper workspace
can monitor an owner or OAuth-authorized Paper account, while new orders stay
behind explicit safety gates and Live remains absent. The GitHub handoff is
documented in [`docs/GITHUB_MIGRATION.md`](docs/GITHUB_MIGRATION.md).
The current screen hierarchy and interaction rules are documented in
[`docs/UI_INFORMATION_ARCHITECTURE.md`](docs/UI_INFORMATION_ARCHITECTURE.md).

The Sites surface can also call this local API when both are used on the same
computer and `uv run tradinglab-dashboard` is running. CORS is limited to the
local development origins and the TradingLAB Sites origin; the API still binds
only to `127.0.0.1` and is not an internet endpoint.

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

### V0.6 portfolio replay

The Portfolio screen now executes the declared V0.6 reference replay against
the real, validated snapshot instead of showing a static allocation sketch:

```bash
uv run tradinglab run-portfolio \\
  --dataset-id ds_20260818T142727647796Z_48e34b6b3110 \\
  --split development \\
  --allocation-method equal_weight \\
  --friction-bps 5 \\
  --output /tmp/tradinglab-v06-development.json
```

The result contains effective dates, decisions, next-open fills, equity curve,
final positions, modeled costs, provenance and safety flags. The fixed V0.6
parameters are SMA200, rebalance every 21 sessions, inverse-volatility
lookback 20 and simulated initial cash of USD 100,000. The interface accepts
only Development and Validation OOS; Project Holdout is intentionally rejected.
