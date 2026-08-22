# V0.6 portfolio research layer

V0.6 adds a small, explicit multi-asset portfolio contract without changing
the V0.1 single-asset strategies or holdout. It supports:

- shared cash across aligned symbols;
- confirmed-close target decisions and next-session-open rebalances;
- long-only integer quantities;
- sell-before-buy ordering;
- equal-weight and inverse-volatility baselines;
- modeled friction and terminal mark-to-market;
- portfolio equity, exposure, turnover, costs, and drawdown metrics.

The allocation methods are predeclared baselines, not automatic optimization.
Vectorized accelerators such as VectorBT may be evaluated later, but this
reference replay remains the contract authority until an independent
comparison exists. No broker, paper, or live execution is present.
