# TradingLAB strategy research results

Date of local run: 2026-08-22.  Dataset: the frozen V0.1 normalized snapshot
`ds_20260818T142727647796Z_48e34b6b3110`.  Friction: 5 bps per executed side.
The research battery contains 45 fixed runs: 3 candidates × 5 assets × 3
splits.  It is separate from the 60-run V0.2 primary reproduction and does not
change V0.1 artifacts or holdout governance.

## Aggregate descriptive results

| Candidate | Split | Median CAGR | Worst CAGR | Median Sharpe | Worst drawdown |
| --- | --- | ---: | ---: | ---: | ---: |
| TSMOM 12M | Development | 6.794% | -2.533% | 0.462 | -43.849% |
| TSMOM 12M | Validation OOS | 0.965% | -2.492% | 0.139 | -29.819% |
| TSMOM 12M | Project Holdout | 4.847% | -3.664% | 0.372 | -36.201% |
| Trend blend 3/6/12M | Development | 6.038% | 4.308% | 0.504 | -34.207% |
| Trend blend 3/6/12M | Validation OOS | 1.871% | 1.330% | 0.239 | -25.657% |
| Trend blend 3/6/12M | Project Holdout | 5.927% | -5.112% | 0.435 | -41.639% |
| Trend-gated mean reversion | Development | 1.045% | 0.071% | 0.210 | -16.600% |
| Trend-gated mean reversion | Validation OOS | 1.814% | 0.524% | 0.585 | -6.541% |
| Trend-gated mean reversion | Project Holdout | 0.626% | -0.223% | 0.223 | -13.769% |

The complete local CSV is generated at
`v0_2_lean/output/research_candidates.csv` and is intentionally ignored by
Git because it is derived from the local market snapshot.

## Interpretation

- The multi-horizon blend is the strongest descriptive candidate in this
  fixed run, but it still has a negative worst holdout CAGR and materially more
  turnover than the 12-month candidate.
- The 12-month candidate is simpler and less active, but it is not universal:
  it has negative CAGR in some asset/split cells.
- The trend-gated mean-reversion candidate reduces drawdown in these samples,
  but its return is correspondingly modest and it is not a promotion candidate.
- These observations are hypotheses, not evidence of future profitability.
  No selection was made using the holdout, no parameter search was run, and no
  strategy was promoted.

## Next research gate

Before any candidate is added to the LEAN adapter, it must pass the independent
LEAN event comparison on a separately identified battery.  The engine battery
must preserve the same next-open, normalized-price, integer-sizing and
friction contracts.  A candidate that looks better only in the offline replay
will be treated as a failed replication, not as a reason to change the engine.
