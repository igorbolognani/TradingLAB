# V0.6 portfolio research layer

V0.6 adds a small, explicit multi-asset portfolio contract without changing
the V0.1 single-asset strategies or holdout. It supports:

- shared cash across aligned symbols;
- confirmed-close target decisions and next-session-open rebalances;
- long-only integer quantities;
- sell-before-buy ordering;
- equal-weight and inverse-volatility baselines;
- modeled friction and terminal mark-to-market;
- portfolio equity, exposure, turnover, costs, drawdown, volatility and Sharpe
  metrics.

The reference replay is usable with the validated local snapshot through:

```bash
uv run tradinglab run-portfolio \
  --dataset-id <validated-dataset-id> \
  --split development \
  --allocation-method equal_weight \
  --friction-bps 5
```

The same operation is available in the private Portfolio screen and through
the local `POST /api/run-portfolio` endpoint. It returns decisions, fills,
equity, final positions, provenance and safety flags. Development and
Validation OOS are supported; Project Holdout is rejected. The fixed
parameters are SMA200, 21-session rebalance, 20-session volatility lookback
and USD 100,000 initial simulated cash.

The allocation methods are predeclared baselines, not automatic optimization.
Vectorized accelerators such as VectorBT may be evaluated later, but this
reference replay remains the contract authority until an independent
comparison exists. No broker, paper, or live execution is present.
