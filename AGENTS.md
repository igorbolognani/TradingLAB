# TradingLAB repository rules

TradingLAB remains a research-first product. It now also contains an
optional, owner-only Alpaca Paper bridge under `site/app/api/alpaca/direct/`.
Preserve the following invariants in every change:

- The research core remains independent of any broker. Do not move broker
  calls into the Python strategy, indicators, backtest adapter, or registry.
- The Paper bridge uses direct HTTPS/WebSocket calls only; do not add a broker
  SDK. Credentials must remain server-side environment variables and must
  never reach browser code, logs, Git, reports, or generated artifacts.
- The bridge is Paper-only and IEX-only. There is no live endpoint, live
  configuration, custody, deposit, payment, or automatic promotion path.
- New Paper orders require all explicit gates: owner identity, `paper`
  environment, `execution_enabled=true`, `paper_enabled=true`, and
  `kill_switch=false`. The default is disabled. Allowlist, integer quantity,
  notional ceiling, fresh quote, long-only sell checks, and broker
  reconciliation remain mandatory.
- Cancellation is a risk-reduction action and may remain available while the
  kill switch blocks new orders. Never weaken the kill switch to make a test
  pass.
- Signals use only confirmed daily regular-session data through close `t` and
  become eligible at the next valid XNYS session open.
- Raw provider data, corporate actions, normalized data, and the declared
  strategy/execution price basis remain separate and auditable.
- Strategies are defined by validated declarative YAML and engine-independent
  Python. Backtesting.py remains replaceable behind the local adapter.
- Historical trials and dataset snapshots are immutable; registry events are
  append-only. Preserve failed and unattractive trials.
- Unit tests stay offline. Network retrieval belongs only to explicit
  integration commands. The direct Alpaca adapter is exercised only with an
  explicitly configured local Paper environment or a separate opt-in check.
- Do not introduce automatic optimization or parameters outside the declared
  V0.1 battery.

Use `uv run` for project commands. Run tests, Ruff, and mypy before committing.
Never commit downloaded Yahoo market rows, broker responses, credentials, or
generated trial artifacts. Push only after explicit authorization.
