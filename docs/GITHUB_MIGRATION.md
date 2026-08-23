# GitHub and Sites migration boundary

The migration is complete for the public research repository. The current
remote is owned by `igorbolognani` and the repository is public:

`https://github.com/igorbolognani/TradingLAB`

The public repository contains code, tests and documentation only. It does not
contain the local Yahoo snapshot, generated trial artifacts, credentials or a
broker path.

## What belongs in GitHub

- Python contracts, strategy specifications, tests, V0.2–V0.6 research bridges.
- The `site/` source for the TradingLAB Research Control Room.
- `.github/workflows/quality.yml` for Python and Sites checks.
- Documentation, lockfiles, and provenance rules.

## What must stay out of GitHub and Sites

- `data/snapshots/`: downloaded Yahoo rows, raw data, actions, and normalized
  snapshots.
- `artifacts/` and `registry/events.jsonl`: generated trials and append-only
  local evidence.
- LEAN, Forex, and portfolio generated inputs/outputs.
- API keys, credentials, cookies, `.env` files, and Sites source-repository
  tokens.

The site does not embed market values. It starts empty and accepts a local
`all_trials.csv` or JSON export in the browser. That keeps the deployed UI
truthful without redistributing the personal/educational Yahoo snapshot. The
local API can run Development or Validation batteries against the local
snapshot; it binds to `127.0.0.1`, exposes no shell, and rejects Project Holdout.

## Safe migration sequence

The original migration checklist was completed as follows:

1. The owner, name and public visibility were confirmed.
2. Ignored data and secret paths were audited before the first push.
3. Python and Sites checks were added to GitHub Actions.
4. `main` was pushed to the remote with the local research code.
5. New changes must repeat the same audit before each push.
6. Sites source must be pushed from the exact committed state, never from a
   directory containing snapshots or credentials.

## What is required for real market data in the deployed site

The current yfinance source is not the distribution contract. A deployed data
surface requires a provider whose terms explicitly permit redistribution or
server-side display, a refresh schedule, a data checksum/provenance manifest,
and a decision about whether only derived aggregates or full OHLC rows are
licensed. The current provider comparison and recommended selection process are
in [`docs/DATA_PROVIDER_RESEARCH.md`](DATA_PROVIDER_RESEARCH.md). This is a
separate data-provider decision, not a frontend change.

V1.0 also defines a provider-neutral `tradinglab.candle.v1` CSV path. It can
be validated and viewed locally without installing yfinance; the private
Yahoo connector is an optional local extra. See
[`docs/V1_0_SPEC.md`](V1_0_SPEC.md).

## What is required for paper/live execution

Paper trading and live trading must be separate, explicitly approved phases.
They require an authenticated backend, secret storage, account/environment
separation, order and fill reconciliation, idempotency, kill switches, audit
logs, rate-limit handling, and human approval. Those capabilities are not added
to V0.1 or the V0.6 reference layer.
