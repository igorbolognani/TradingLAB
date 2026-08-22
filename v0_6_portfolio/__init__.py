"""Deterministic multi-asset portfolio research for V0.6."""

from .contract import PortfolioBar, PortfolioDecision, PortfolioResult
from .replay import build_trend_decisions, replay_portfolio

__all__ = [
    "PortfolioBar",
    "PortfolioDecision",
    "PortfolioResult",
    "build_trend_decisions",
    "replay_portfolio",
]
