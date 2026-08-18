# TradingLAB V0.1 authoritative specification

## Scope and exclusions

V0.1 implements local Python research with Backtesting.py, explicit yfinance
retrieval, immutable raw/action/normalized snapshots, causal daily strategies,
canonical ledgers and metrics, an append-only trial registry, and the declared
robustness battery over SPY, IWM, EFA, TLT, and GLD.

It excludes Alpaca, LEAN, TradingView/Pine, MT5/MQL5, VectorBT, machine
learning, portfolio construction, intraday/extended-hours data, shorting,
leverage, fractional shares, options/futures/crypto, automatic optimization,
frontends, servers, databases, and cloud infrastructure.

## Market-data contract

- Requested interval: daily regular-session bars.
- Requested range: `2005-01-01` through exclusive `2026-01-01`.
- Accepted rows: XNYS sessions only, normalized to `America/New_York`, never
  any 2026 observation.
- The installed exchange-calendars 4.13.2 XNYS calendar is materialized with
  explicit requested bounds padded by seven calendar days and `side="both"`;
  padding admits weekend/holiday boundary labels without changing accepted
  sessions. This avoids the rolling default window and makes the 2005 warm-up
  range independently valid.
- Provider: yfinance/Yahoo for personal educational/research use only.
- Retrieval sets every material semantic argument explicitly and records the
  installed provider version, signature, exact arguments, source index/timezone,
  effective range, row counts, missing values, missing sessions, and hashes.
- A refresh creates a new immutable dataset identity and never overwrites a
  prior snapshot.

The installed yfinance 1.6.0 connector uses these exact `Ticker.history`
semantics: `period=None`, explicit start and exclusive end, `interval="1d"`,
`prepost=False`, `actions=True`, `auto_adjust=False`, `back_adjust=False`,
`repair=False`, `keepna=True`, `rounding=False`, `timeout=30`, and
`yf.config.debug.hide_exceptions=False`; the deprecated per-call `raise_errors`
is explicitly recorded as unused. `group_by`, `multi_level_index`, `threads`,
and `ignore_tz` are recorded as not applicable to the single-ticker API. The
provider index timezone is preserved in RAW and explicitly normalized to
`America/New_York` downstream.

Each symbol snapshot has three layers:

1. Raw provider OHLCV, provider adjusted close, actions, and metadata.
2. Separate corporate actions (`Dividends`, `Stock Splits`, `Capital Gains`).
3. Normalized research data using normalization `ohlc_total_return_v1`:
   `factor_t = Adj Close_t / raw Close_t` and
   `normalized OHLC_t = raw OHLC_t * factor_t` for the same positive factor.
   Volume is preserved for provenance and unused by strategies.

Normalized Close must reconcile to provider adjusted close. Indicators use
normalized Close and modeled fills use corresponding normalized Open. Embedded
dividends are not credited again. Invalid required OHLC is not silently filled,
dropped, or repaired.

## Causal and execution contract

```text
confirmed close t -> decide from information through t -> next XNYS open fill
```

No partial bar or future row enters a signal. Rolling indicators use explicit
`min_periods`. Each split starts with USD 100,000 and no position. Pre-split
rows may warm indicators and establish the first eligible decision, but no
pre-split position, return, or P&L is carried in. Long/cash only, one position,
integer shares, no leverage, no pyramiding, and zero cash interest apply.

At an entry fill:

```text
estimated_cost_per_share = normalized_open * (1 + friction_bps / 10000)
quantity = floor(available_cash / estimated_cost_per_share)
modeled_cost = abs(quantity * normalized_open) * friction_bps / 10000
```

Friction is modeled once per actual entry and exit fill. The base is 5 bps per
side; sensitivities are 0, 5, 10, and 25 bps. Spread is zero. Remaining open
positions are marked to the final normalized Close without a fictional exit or
exit cost, and remain explicitly open in the ledger.

The installed Backtesting.py 0.6.6 reference replay sets `cash=100000`,
`spread=0`, relative `commission=friction_bps/10000`, `margin=1`,
`trade_on_close=False`, `hedging=False`, `exclusive_orders=True`, and
`finalize_trades=False`. Installed source inspection confirms market orders
fill on the next open in this mode, commission is applied at both actual sides,
and open terminal trades are not force-closed. Canonical ledgers remain
authoritative for exact V0.1 accounting.

## Evaluation periods

| Split | Inclusive dates |
| --- | --- |
| Development | 2007-01-01 to 2014-12-31 |
| Validation OOS | 2015-01-01 to 2019-12-31 |
| Project Holdout | 2020-01-01 to 2025-12-31 |

The holdout is executed only as the controlled final battery. Viewing it marks
it seen; later changes require a new strategy version and new immutable trials.

## Strategies and validation battery

Validated declarative YAML under `strategy_specs/` is canonical. Python maps
enumerated rule identifiers to engine-independent indicator/decision logic.
The fixed strategies are CASH, matching-asset Buy & Hold, SMA200 Trend, and
20-session z-score Mean Reversion exactly as their specifications declare.

Primary Trend uses SMA 200. Primary Mean Reversion uses lookback 20, entry
z-score -2.0, exit z-score 0.0, and maximum hold 10 sessions. One-at-a-time
sensitivities are Trend SMA 150/200/250 and Mean Reversion lookback 15/20/25,
entry z-score -1.5/-2.0/-2.5, or max hold 5/10/15, deduplicating primary.
Parameter sensitivity always uses 5 bps. Friction sensitivity uses only frozen
primary parameters. No optimizer or Cartesian parameter/friction product is
allowed.

## Canonical metrics and artifacts

Engine-independent metrics use 252 sessions/year and zero risk-free rate:
total return, CAGR, sample annualized volatility, Sharpe, max drawdown,
end-of-session exposure, fill-notional turnover, initiated position lifecycle
count, modeled costs, and gross-to-net cost drag. Undefined values serialize as
JSON null/blank CSV cells, never infinity. Matching-asset Buy & Hold deltas use
the same split and friction.

Each immutable trial directory contains `manifest.json`, `metrics.csv`,
`trades.csv`, `equity_curve.csv`, `signals.csv`, `report.md`, and `plots/` when
applicable. Volatile identity metadata is excluded from canonical analytical
hashes. The append-only JSONL registry writes `started` before execution and a
terminal `completed` or `failed` event afterward.

## Deferred decisions

- Strategy promotion criteria: after V0.1 results and independent V0.2 LEAN
  reproduction.
- Alpaca execution semantics: V0.3 only.
- MT5 broker, currencies, and timeframes: future MT5 phase.
- Commercial data provider: before any non-personal/commercial use.
- Backtest engine/license architecture: before distribution or commercial use.

No blocking conceptual decisions remain for V0.1 implementation.
