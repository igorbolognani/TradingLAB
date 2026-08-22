# V0.3–V0.5 pilot implementation

This document is the durable handoff for the roadmap after the frozen V0.1
laboratory and completed V0.2 LEAN reproduction. The repository advances the
research contracts through V0.5 without adding a broker execution capability.

## Product map

```text
V0.1 local ETF research
  -> V0.2 independent LEAN reproduction
  -> V0.3 paper-readiness contracts + deterministic forward simulator
  -> V0.4 TradingView visual/alert observation
  -> V0.5 EURUSD D1 offline Forex/MT5 research bridge
  -> V0.6 multi-asset portfolio reference layer
  -> human gates before any external account or terminal
```

The repository remains one product repository. These phases complement one
another because they answer different questions, but they do not share an
implicit execution channel:

| Phase | Question | Implemented evidence | Explicitly absent |
| --- | --- | --- | --- |
| V0.1 | Can simple ETF hypotheses be tested causally? | Frozen local dataset, canonical ledger, registry, holdout | Broker code |
| V0.2 | Does the primary contract survive another engine? | 60/60 primary LEAN comparisons | Strategy promotion |
| V0.3 | Can a decision be observed and reconciled safely? | Manifest gate, intent/fill schema, local simulator | Alpaca SDK, API, order submission |
| V0.4 | Does visual triage help formulate a hypothesis? | Pine v6 confirmed-bar observer and parser | Pine as canonical engine or executor |
| V0.5 | Can the methodology be tested on a different market? | UTC Forex CSV contract and causal EURUSD D1 replay | MT5 connection, broker history, EA |
| V0.6 | Can several research signals share capital transparently? | Reference portfolio replay and allocation baselines | Broker execution, automatic optimization |

## V0.3 — Paper readiness, not paper execution

`v0_3_paper/` implements the boundary that must exist before a future paper
adapter is even considered:

1. `PaperManifest` binds strategy, version, experiment, dataset, spec, and the
   V0.2 comparison report into one SHA-256 fingerprint.
2. `PromotionState` makes `research -> candidate -> paper-approved -> disabled`
   explicit and human-gated. Metrics cannot promote a strategy automatically.
3. `ExecutionIntent` records the confirmed decision and next eligible session.
4. `simulate_forward` produces deterministic local observations from supplied
   opening prices. It has no network, credential, or order API surface.
5. `reconcile` preserves missing, rejected, duplicate, unexpected, and mismatched
   observations instead of treating them as successful fills.

The initial pilot length is 60 sessions as an observation budget, not an
acceptance criterion. A later Alpaca phase would require a new, separately
approved adapter and an operational review.

### Open decision resolved: future Alpaca order semantics

The frozen V0.1 contract decides after the close and becomes eligible at the
next open. If an external Alpaca adapter is approved later, the default design
should be an equity market-on-open order (`type=market`, `time_in_force=opg`),
with an explicit rejection/cancellation path. A limit-on-open order could be
used only if a limit policy is separately specified. This is a design decision
for a future gate, not code in this repository.

Alpaca documents that `opg` is eligible only for the opening auction and that
unfilled orders are cancelled. Its paper environment also has different fill,
liquidity, latency, and dividend assumptions from the V0.1 total-return
research basis. Therefore, paper P&L would require an explicit reconciliation
report and would not replace the backtest evidence.

## V0.4 — TradingView observation

`v0_4_tradingview/pine/tradinglab_v04_observer.pine` is a Pine Script v6
indicator, not a strategy. It:

- observes only `TREND_SMA200_V1` or `MEANREV_Z20_V1`;
- requires `barstate.isconfirmed`;
- emits a small JSON observation with no quantity, order, broker, endpoint, or
  credential fields;
- uses `alert.freq_once_per_bar_close`;
- never calls `strategy.*` or an external endpoint.

The Python bridge validates payloads locally. A chart symbol, timeframe,
regular-session setting, price basis, script revision, and alert configuration
must be recorded for any comparison. TradingView alerts are configured in its
chart UI and are not created merely by adding this file. The TradingView chart
is not the source of truth for the frozen dataset, and a visual match is not a
second-engine reproduction.

## V0.5 — Forex / MT5 research bridge

The first pilot is deliberately narrow:

- symbol: `EURUSD`;
- timeframe: daily;
- timestamp contract: explicit UTC;
- execution hypothesis: decision after bar close, next bar open;
- strategy family: a separate temporal trend research strategy;
- input: offline CSV, never an implicit broker download;
- output: signals, fills, and terminal mark-to-market from a local replay.

`v0_5_forex/mql5/TradingLabObserver.mq5` is an indicator-only observer. A
future MT5 Strategy Tester experiment must first freeze a custom-symbol or
history fixture and record broker/session metadata, contract size, spread,
rollover, timezone, and source checksum. Forex bars must not be inserted into
the XNYS ETF registry or described as a direct transfer of V0.1 results.

## Promotion and evidence policy

There is no universal Sharpe threshold. Before a human can approve an external
paper observation, the evidence packet must include:

1. the frozen V0.1 result and its already-seen holdout status;
2. the completed V0.2 primary comparison;
3. unresolved warnings and data gaps, not only passing metrics;
4. explicit strategy version, dataset, code, and lockfile fingerprints;
5. a defined observation budget and reconciliation procedure;
6. a written decision that does not promote solely because one return or Sharpe
   value is attractive.

Changing a strategy after the observed holdout creates a new strategy version,
new specification, new dataset/experiment linkage, and a new reserved period.

## Decisions that remain deferred

- A licensed/commercial data provider is required before redistribution or
  commercial use; yfinance remains personal/educational research input.
- Backtesting.py's AGPL boundary must be reviewed before distribution or a
  hosted/commercial product.
- An actual Alpaca account/adapter remains outside this repository's safety
  contract and requires an explicit future authorization.
- A broker-specific MT5 test requires choosing the broker, symbol contract,
  timezone, and history source at the time of that experiment.
- Portfolio construction, VectorBT, ML, and automatic optimization remain
  later research questions, not hidden additions to V0.1. V0.6 now has only a
  reference contract; an accelerator must reproduce it before adoption.

## Official references used for the contracts

- [Alpaca paper trading](https://docs.alpaca.markets/us/docs/paper-trading)
  documents the IEX-only paper account boundary and the differences in
  dividends, latency, impact, queue position, and fill assumptions.
- [Alpaca order handling](https://docs.alpaca.markets/us/docs/orders-at-alpaca)
  documents `opg` as market-on-open/limit-on-open time-in-force and its opening
  auction cancellation behavior.
- [TradingView alerts](https://www.tradingview.com/pine-script-docs/concepts/alerts/)
  documents confirmed-bar alert configuration and the distinction between
  `alert()` and `alertcondition()`.
- [TradingView execution model](https://www.tradingview.com/pine-script-docs/language/execution-model/)
  is the reference for treating the chart script as an observation surface,
  not the canonical research engine.
- [MQL5 custom symbols](https://www.mql5.com/en/docs/customsymbols) and the
  [MQL5 Strategy Tester](https://www.mql5.com/en/docs/runtime/testing) are the
  future manual references for frozen Forex history and tester setup.
