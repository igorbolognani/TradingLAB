# TradingLAB V0.2 independent LEAN reproduction

## Purpose

V0.2 reproduces the frozen V0.1 research contract in a second execution
implementation using QuantConnect LEAN. It is not a strategy revision and it
does not reopen V0.1 decisions.

The repository remains one product repository. The implementation boundary is
`v0_2_lean/`; it does not import `src/tradinglab` and it does not write the
V0.1 registry or artifacts.

## Acceptance dimensions

1. `CASH_0_V1` and `BUY_HOLD_V1` controls.
2. `TREND_SMA200_V1`.
3. `MEANREV_Z20_V1`.
4. SPY, IWM, EFA, TLT and GLD over Development, Validation OOS and Project
   Holdout.
5. Confirmed-close decisions, next-open eligibility, integer long-only sizing,
   one modeled friction charge per executed side, and terminal mark-to-market.
6. Explicit comparison with the frozen V0.1 primary artifacts and documented
   numeric tolerances.

## Data boundary

V0.2 consumes only locally prepared normalized CSVs derived from the frozen
V0.1 dataset manifest. It does not read raw Yahoo rows or corporate-action
files inside the LEAN algorithm. The normalized research basis remains:

```text
factor_t = adjusted_close_t / raw_close_t
normalized_ohlc_t = raw_ohlc_t * factor_t
```

The LEAN custom data class receives one explicit normalized daily bar. The
preparation step is local and produces ignored files under
`v0_2_lean/lean_data/`.

## Reproduction boundary

The V0.2 replay and LEAN algorithm independently encode the four frozen
strategies. The replay is an offline oracle for deterministic comparison. A
LEAN run is separate evidence and must produce an engine result before it can
be called an engine validation.

V0.2 does not implement optimization, strategy promotion, portfolio
construction, broker access, paper/live execution, or a new holdout.

## Current validation state

- Independent primary replay: 60/60 V0.1 primary configurations match inside
  the declared tolerances.
- Synthetic V0.2 tests cover controls, frozen parameters, next-open sizing and
  friction.
- LEAN CLI project and custom-data algorithm are implemented.
- Official LEAN image `quantconnect/lean:17998` is available locally and its
  digest is recorded in the V0.2 README.
- SPY Project Holdout smoke runs passed for CASH, Buy & Hold, Trend SMA200 and
  Mean Reversion Z20, including the custom-data path, next-open fill model and
  modeled fees.
- The engine runner now stages clean LEAN projects, captures structured signal
  and fill events, and validates them against the independent replay.  A SPY
  Development smoke check currently passes for CASH, Buy & Hold, Trend SMA200
  and Mean Reversion Z20 after timezone, warm-up and fill-price corrections.
- Full LEAN engine comparison completed: 60/60 configurations passed with zero
  runtime errors and zero signal/fill contract divergences.  The engine image
  was `quantconnect/lean:17998` with digest
  `sha256:c76cf4f7bc88f16986a671c27e8107a2f9606eb5a67c8ac817a04f76feb5502f`.
- The engine comparison validates event and execution-contract equivalence;
  it does not promote any strategy or prove future economic performance.

## Research-only strategy extension

Three fixed candidates were evaluated separately across the same 5 × 3 grid:
12-month time-series momentum, a 3/6/12-month equal-vote trend blend, and a
trend-gated Z20 mean-reversion blend.  The candidates live in
`v0_2_lean/research_candidates.py` and are documented in
`docs/STRATEGY_RESEARCH.md`.  They do not modify the V0.1 primary strategies,
the V0.2 primary contract, the registry or holdout governance.  They must not
be promoted or added to the LEAN adapter until the primary engine battery is
complete and a separate candidate-engine battery is approved.
