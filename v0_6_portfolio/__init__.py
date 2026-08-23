"""Deterministic multi-asset portfolio research for V0.6."""

from .contract import PortfolioBar, PortfolioDecision, PortfolioResult
from .replay import build_trend_decisions, replay_portfolio
from .service import PortfolioRun, frames_to_portfolio_bars, run_trend_portfolio

__all__ = [
    "PortfolioBar",
    "PortfolioDecision",
    "PortfolioResult",
    "PortfolioRun",
    "build_trend_decisions",
    "frames_to_portfolio_bars",
    "replay_portfolio",
    "run_trend_portfolio",
]
