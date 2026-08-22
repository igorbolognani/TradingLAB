"""TradingView observation bridge; it deliberately has no execution adapter."""

from .bridge import TradingViewSignal, parse_alert_payload

__all__ = ["TradingViewSignal", "parse_alert_payload"]
