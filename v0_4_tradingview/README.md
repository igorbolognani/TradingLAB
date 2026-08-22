# V0.4 TradingView observer bridge

This phase adds a Pine Script v6 observer for visual triage and confirmed-bar
alerts. It is not the canonical strategy implementation and it cannot submit
orders. The Python contracts in `bridge.py` only parse and validate an
observation payload locally.

The indicator intentionally uses `barstate.isconfirmed`, emits no quantity,
broker, endpoint, credential, or order fields, and uses
`alert.freq_once_per_bar_close`. A TradingView user must configure any alert
manually in the chart UI; adding the Pine file does not create a running alert.

The chart symbol, chart timeframe, session treatment, and price basis must be
recorded when comparing an observation with V0.1/V0.2. TradingView remains a
triage surface, not evidence that replaces the frozen normalized dataset or
the independent LEAN reproduction.
