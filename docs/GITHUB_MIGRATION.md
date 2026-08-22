# GitHub and Sites migration boundary

This repository is ready to be placed in a GitHub repository, but the remote
identity and visibility have not been chosen. No remote, token, commit, or push
is created by this document.

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

1. Confirm the intended GitHub owner, repository name, and private/public
   visibility.
2. Review `git status`, `git diff --stat`, and `git diff -- .gitignore`.
3. Confirm no ignored data or secret has been force-added.
4. Run the Python and site checks from the root and `site/` directories.
5. Create a reviewable local commit only after the exact file set is approved.
6. Add the exact GitHub remote and push `main` only with explicit approval.
7. Configure GitHub Actions and Sites from the committed source, never from a
   directory containing snapshots or credentials.

## What is required for real market data in the deployed site

The current yfinance source is not the distribution contract. A deployed data
surface requires a provider whose terms explicitly permit redistribution or
server-side display, a refresh schedule, a data checksum/provenance manifest,
and a decision about whether only derived aggregates or full OHLC rows are
licensed. This is a separate data-provider decision, not a frontend change.

## What is required for paper/live execution

Paper trading and live trading must be separate, explicitly approved phases.
They require an authenticated backend, secret storage, account/environment
separation, order and fill reconciliation, idempotency, kill switches, audit
logs, rate-limit handling, and human approval. Those capabilities are not added
to V0.1 or the V0.6 reference layer.
