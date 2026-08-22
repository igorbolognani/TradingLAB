"""Engine-independent V0.6 portfolio contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

AllocationMethod = Literal["equal_weight", "inverse_vol"]


@dataclass(frozen=True, slots=True)
class PortfolioBar:
    """A normalized daily bar used by the portfolio layer."""

    session: date
    symbol: str
    open: float
    close: float

    def validate(self) -> None:
        if not self.symbol:
            raise ValueError("portfolio bar symbol is required")
        if self.open <= 0 or self.close <= 0:
            raise ValueError("portfolio prices must be positive")


@dataclass(frozen=True, slots=True)
class PortfolioDecision:
    """A close-time target universe for a later open rebalance."""

    decision_session: date
    execution_session: date
    target_symbols: tuple[str, ...]

    def validate(self) -> None:
        if self.execution_session <= self.decision_session:
            raise ValueError("portfolio execution must follow the decision")
        if len(set(self.target_symbols)) != len(self.target_symbols):
            raise ValueError("portfolio target symbols must be unique")


@dataclass(frozen=True, slots=True)
class PortfolioFill:
    session: date
    symbol: str
    side: str
    quantity: int
    price: float
    modeled_cost: float


@dataclass(frozen=True, slots=True)
class PortfolioPoint:
    session: date
    cash: float
    gross_equity: float
    net_equity: float
    invested_symbols: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PortfolioResult:
    strategy_id: str
    allocation_method: AllocationMethod
    initial_cash: float
    fills: tuple[PortfolioFill, ...]
    equity: tuple[PortfolioPoint, ...]
    metrics: dict[str, float | int | None]
