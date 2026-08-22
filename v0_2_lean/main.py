"""LEAN CLI entry point for the V0.2 algorithm project."""

from algorithms.tradinglab_v02 import TradingLabV02Algorithm as _TradingLabV02Algorithm


class TradingLabV02Algorithm(_TradingLabV02Algorithm):
    """Expose the algorithm class from the LEAN entry module."""

    pass


__all__ = ["TradingLabV02Algorithm"]
