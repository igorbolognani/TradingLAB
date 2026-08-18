# Engineering owner comprehension

## Mental model

1. `data_source/yfinance_source.py` is the only network/provider boundary.
2. `data/normalization.py` converts explicit unadjusted provider rows into one
   coherent total-return OHLC basis; manifests and hashes freeze provenance.
3. Declarative YAML is validated and hashed before domain indicator and state
   logic can run.
4. `BacktestingPyAdapter` applies next-open integer fills and the single
   friction translation, while emitting audit ledgers rather than relying on
   engine summary statistics.
5. Canonical metrics consume only those ledgers. Trials bind code, spec, data,
   assumptions, metrics, and reports through immutable IDs and append-only
   events.

The fragile boundaries are session timezone/calendar normalization, adjusted
OHLC coherence, split-boundary warm-up without P&L carry, max-hold counting,
and preventing friction from being charged twice.

## Knowledge gaps

None currently.

## Resolved knowledge gaps

- Installed yfinance 1.6.0 exposes the explicit history arguments recorded in
  `MVP_SPEC.md`; network retrieval is isolated and opt-in.
- Installed Backtesting.py 0.6.6 executes market orders at next open when
  `trade_on_close=False`, commissions both actual sides, and preserves terminal
  positions when `finalize_trades=False`. Adapter fixtures cover the translation.
