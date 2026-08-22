# V0.5 Forex / MT5 research bridge

The first V0.5 pilot is `EURUSD` on daily bars with explicit UTC timestamps.
The Python importer and replay are offline and broker-neutral. They provide a
causal next-bar-open research contract; they do not connect to a MetaTrader
terminal, download broker history, or submit an order.

The `mql5/TradingLabObserver.mq5` file is an indicator-only visual observer.
It has no Expert Advisor lifecycle, trade class, order function, credential,
or network operation. Any future MT5 Strategy Tester run must use a separately
approved custom-symbol/history fixture and must record the broker, symbol,
contract size, spread model, timezone, rollover, and data provenance.

Forex sessions are not XNYS sessions. Results from this directory must not be
merged into the V0.1 ETF registry or treated as evidence that the equities
strategies transfer to a currency market.
