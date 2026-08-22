# TradingLAB strategy research extension

Status: research candidates only.  This document does not modify the frozen
V0.1 strategies, the V0.2 primary battery, the V0.1 holdout, or the registry.

## Research standard

“High quality” is assessed by evidence quality, not by an internet popularity
score.  A candidate must have a transparent rule, a credible original paper or
institutional research source, a clear data requirement, and a feasible test
under the TradingLAB causal execution contract.  A published backtest is not a
promotion signal: multiple-testing, costs, regime dependence and replication
remain unresolved until tested here.

The primary warnings come from research on data snooping and backtest
overfitting.  Trying more configurations increases the chance of selecting a
false winner, and apparent technical-rule outperformance often weakens after
out-of-sample and multiple-testing controls.  The candidate set below is
therefore fixed before this local evaluation and has no automatic optimizer.

## Evidence review

| Family | Source quality | What the literature supports | Fit to this lab |
| --- | --- | --- | --- |
| Time-series momentum / trend following | Strong: original academic paper plus long-history AQR/academic evidence | Positive persistence over roughly 1–12 months across equity-index, currency, commodity and bond futures; long-run trend-following evidence across many decades | Good as a long-only daily ETF hypothesis, with the caveat that the original evidence is broader than five ETFs |
| Multi-horizon signal aggregation | Moderate-to-strong: academic/institutional quantitative research | Aggregating signals across horizons can represent trend strength and reduce dependence on one horizon | Good as a pre-registered equal-vote candidate; not a claim that the blend is optimal |
| Momentum plus reversal | Moderate: academic research supports different horizons for continuation and reversal; exact rules are model-dependent | Short/medium-term continuation and longer-horizon reversal can coexist; combinations may diversify, but implementation is sensitive | Test only as a simple trend-gated pullback, not as a dynamically optimized blend |
| Cross-sectional momentum/value | Strong evidence in the literature, but different structure | Cross-sectional ranking and value require multiple instruments and often long/short or valuation data | Excluded from this stage; current lab runs one asset at a time and has no portfolio universe |
| Pairs/statistical arbitrage | Strong original evidence, but requires pair selection and spread accounting | Relative-value profits depend on matched instruments, portfolio construction and temporary mispricing | Excluded from this stage; would require a new multi-asset contract |
| Futures term structure | Strong in futures research, not transferable to ETF OHLC alone | Carry/contango/backwardation can complement momentum in futures | Excluded until a futures data contract exists |
| ML, sentiment and large technical-rule searches | Low fit for the current stage | Flexible searches magnify leakage and backtest-overfitting risk | Excluded; no model, training pipeline or unregistered search is introduced |

## Sources

1. Moskowitz, Ooi and Pedersen, *Time Series Momentum*, Chicago Booth Research
   Paper 12-21 / SSRN 2089463:
   https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463
2. Hurst, Ooi and Pedersen, *A Century of Evidence on Trend-Following
   Investing*, SSRN 2993026:
   https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026
3. Baltas and Kosowski, *Demystifying Time-Series Momentum Strategies*, SSRN
   2140091:
   https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2140091
4. Elaut and Erdos, *Trends’ Signal Strength and the Performance of CTAs*,
   SSRN 2772047:
   https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2772047
5. Asness, Moskowitz and Pedersen, *Value and Momentum Everywhere*, SSRN
   2174501:
   https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2174501_code753937?abstractid=2174501
6. Liu and Papailias, *Time series reversal in trend-following strategies*,
   SSRN 2971875:
   https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2971875
7. Gatev, Goetzmann and Rouwenhorst, *Pairs Trading: Performance of a Relative
   Value Arbitrage Rule*, SSRN 141615:
   https://papers.ssrn.com/sol3/papers.cfm?abstract_id=141615
8. Harvey, Liu and Zhu, *...and the Cross-Section of Expected Returns*, SSRN
   2249314:
   https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2249314
9. Bailey, Borwein, López de Prado and Zhu, *The Probability of Backtest
   Overfitting*, SSRN 2308659:
   https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659
10. Sullivan, Timmermann and White, *Data-Snooping, Technical Trading Rule
    Performance, and the Bootstrap*, Journal of Finance, 1999.  The rule-search
    and bootstrap warning is retained as a design constraint even where a
    public full-text link is unavailable.

## Frozen candidates

The candidate IDs are not V0.1 strategies and are not promotion decisions.
They are intentionally small and fixed:

### `TSMOM_12M_RESEARCH_V1`

At confirmed close `t`, compute the normalized-close return over 252 prior
sessions.  Enter long at the next valid open when the return is positive; exit
at the next valid open when it is non-positive.  Use integer long-only sizing
and the existing 5 bps research friction.

This is a single-asset approximation of time-series momentum.  The original
papers study a broader futures universe, so success on these ETFs would still
be a local result, not a universal claim.

### `TREND_BLEND_3_6_12_RESEARCH_V1`

At close `t`, compute the signs of 63-, 126- and 252-session returns.  Enter
when at least two of three are positive; exit when at least two of three are
non-positive; otherwise keep the current state.  The equal vote is fixed in
advance and is not optimized on the holdout.

This implements a transparent signal-strength/ensemble hypothesis while
limiting degrees of freedom.

### `TREND_GATED_MEANREV_RESEARCH_V1`

At close `t`, require both a positive 200-session trend regime and a 20-session
z-score at or below -2 to enter.  Exit when the trend regime is lost, the
z-score reaches zero, or ten held sessions are reached.  All fills remain
next-open and all inputs are confirmed close data.

This is a deliberately conservative “buy a pullback inside an uptrend” blend.
It reuses V0.1 thresholds to avoid introducing a tuning exercise; it is a
hypothesis inspired by the literature on momentum/reversal coexistence, not a
claim that the cited papers prescribe this exact rule.

## Validation gates

1. Run the fixed candidate battery offline across the same five assets and
   three temporal splits.
2. Preserve every result, including negative or unstable results; do not rank
   by holdout return alone.
3. Compare each candidate with the corresponding Buy & Hold and the V0.1
   primary strategies using return, CAGR, Sharpe, drawdown, exposure, turnover,
   trade count and modeled costs.
4. Apply the same causal, next-open, friction and data-provenance checks.
5. Only after the offline review, implement candidates in the independent LEAN
   adapter and run a separately identified engine battery.
6. No candidate is promoted to V0.1, no new holdout is opened, and no broker or
   paper/live capability is introduced by this research extension.
