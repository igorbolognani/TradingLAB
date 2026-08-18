# TradingLAB repository rules

This repository is a local quantitative research laboratory, not a trading
system. Preserve the following invariants in every change:

- Broker execution code does not exist. Do not add broker SDKs, credentials,
  order-submission calls, `live` environments, or paper-trading execution.
- Signals use only confirmed daily regular-session data through close `t` and
  become eligible at the next valid XNYS session open.
- Raw provider data, corporate actions, normalized data, and the declared
  strategy/execution price basis remain separate and auditable.
- Strategies are defined by validated declarative YAML and engine-independent
  Python. Backtesting.py remains replaceable behind the local adapter.
- Historical trials and dataset snapshots are immutable; registry events are
  append-only. Preserve failed and unattractive trials.
- Unit tests stay offline. Network retrieval belongs only to explicit
  integration commands.
- Do not introduce automatic optimization or parameters outside the declared
  V0.1 battery.

Use `uv run` for project commands. Run tests, Ruff, and mypy before committing.
Never commit downloaded Yahoo market rows or generated trial artifacts, and
never push without explicit authorization.

