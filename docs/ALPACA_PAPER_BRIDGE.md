# Alpaca Paper bridge

Status: implemented and verified locally; new order submission remains
disabled by the current safety configuration.

This document describes the narrow online integration added around the
research-first TradingLAB. It does not change the V0.1 research contract or
promote any strategy.

## What exists

The bridge lives under `site/app/api/alpaca/direct/` and uses direct HTTPS and
WebSocket requests. It does not install an Alpaca SDK. The browser never sees
`ALPACA_API_KEY` or `ALPACA_API_SECRET`; those values are read only by the
server runtime.

The server forces:

- execution environment: `paper`;
- market-data feed: `iex`;
- trading endpoint: `https://paper-api.alpaca.markets`;
- market-data endpoint: `https://data.alpaca.markets`;
- stock stream: `wss://stream.data.alpaca.markets/v2/iex`.

The owner gate accepts the configured ChatGPT user ID or email. Unauthenticated
localhost access is allowed only for local development. Public visitors and
non-owner accounts cannot call the direct routes.

## Routes

| Route | Purpose |
| --- | --- |
| `GET /api/alpaca/direct/status` | Safe configuration and gate status; never returns credentials |
| `GET /api/alpaca/direct/quote?symbol=SPY` | WebSocket quote with REST fallback and explicit freshness |
| `GET /api/alpaca/direct/bars?symbol=SPY&timeframe=1Min&limit=120` | Real IEX OHLCV candles and calculated fields |
| `GET /api/alpaca/direct/account` | Paper account state |
| `GET /api/alpaca/direct/positions` | Current Paper positions |
| `GET /api/alpaca/direct/orders?status=open` | Orders and reconciliation fields |
| `POST /api/alpaca/direct/orders` | New Paper order, gated and risk-limited |
| `DELETE /api/alpaca/direct/orders?id=<id>` | Cancel one order; without `id`, cancel all open orders |

## Safety contract

The following defaults keep the product in observation mode:

```text
TRADINGLAB_EXECUTION_ENABLED=false
TRADINGLAB_PAPER_ENABLED=false
TRADINGLAB_LIVE_ENABLED=false
TRADINGLAB_KILL_SWITCH=true
```

Even if new Paper orders are explicitly enabled later, the server still
requires owner identity, Paper configuration and IEX feed, and checks:

- symbol allowlist: `SPY,IWM,EFA,TLT,GLD` by default;
- integer quantity and maximum quantity;
- maximum order notional, US$500 by default;
- a fresh quote, no older than 120 seconds;
- long-only sells that do not exceed the broker-reported position;
- broker-generated order status and client-order ID for reconciliation.

Cancellation remains available while the kill switch is active because it
reduces exposure rather than creating it. There is no live URL or flag that
can be selected by this bridge.

## Data meaning

`realtime_active=true` means that the server received a matching quote through
the Alpaca IEX WebSocket during that request. If the WebSocket fails or the
market has no quote, the server may return the latest REST quote but marks
`realtime_active=false`, `latency_ms=null` and reports `data_age_seconds`.
This distinction prevents an old quote from being presented as real-time.

Candles expose the provider, provider version, retrieval time, UTC timezone,
price basis and completeness. Alpaca IEX data is a live-provider response, not
the immutable XNYS/yfinance research snapshot; the two datasets must not be
mixed silently.

## OAuth boundary

The Alpaca OAuth screen already exists separately and requests data access for
the owner’s approved Connect application. Application approval is still a
provider review state, not an implementation fact. OAuth tokens and direct
Paper API credentials are different mechanisms. OAuth approval is not required
for the owner’s local direct Paper monitor, and it does not enable orders in
the current bridge.

Official provider references:

- [Using OAuth2 and Trading API](https://docs.alpaca.markets/us/docs/using-oauth2-and-trading-api)
- [Registering Your App](https://docs.alpaca.markets/us/docs/registering-your-app)
- [About Connect API](https://docs.alpaca.markets/us/docs/about-connect-api)
- [Market data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)
- [Streaming market data](https://docs.alpaca.markets/us/v1.1/docs/streaming-market-data)

## Verification record

The local Paper environment was checked without submitting or cancelling an
order:

- configuration was recognized as Paper/IEX with execution disabled and kill
  switch active;
- the Paper account endpoint responded with an active USD account;
- positions and open orders were read successfully and were empty at the
  time of the check;
- real IEX bars were returned for daily and intraday requests;
- the WebSocket path was attempted; when no quote was available, the REST
  fallback was marked non-realtime rather than fabricating latency;
- the web build, lint, rendered-site tests and local route checks passed.

This proves connectivity and contract behavior at the time of the check. It
does not prove fill quality, exchange-level latency, profitability, or live
trading readiness.
