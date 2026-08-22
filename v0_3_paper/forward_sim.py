"""Deterministic forward-fill simulator with no external execution path."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from v0_3_paper.contract import (
    ExecutionIntent,
    ExecutionSide,
    ObservationStatus,
    ObservedExecution,
)


@dataclass(frozen=True, slots=True)
class ForwardSimulation:
    """The complete local observation result."""

    observations: tuple[ObservedExecution, ...]
    final_cash: float
    final_positions: tuple[tuple[str, int], ...]


def _rejected(intent: ExecutionIntent, source: str) -> ObservedExecution:
    return ObservedExecution(
        intent_id=intent.intent_id,
        status=ObservationStatus.REJECTED,
        observed_session=None,
        side=None,
        quantity=0,
        price=None,
        modeled_cost=0.0,
        source=source,
    )


def simulate_forward(
    intents: tuple[ExecutionIntent, ...] | list[ExecutionIntent],
    *,
    opening_prices: Mapping[date, float],
    initial_cash: float = 100_000.0,
    source: str = "local-forward-simulator",
) -> ForwardSimulation:
    """Simulate next-session observations from supplied local opening prices.

    The function is intentionally data-only: it does not know an API endpoint,
    credential, broker client, or order-submission operation.
    """

    if not math.isfinite(initial_cash) or initial_cash <= 0:
        raise ValueError("initial_cash must be finite and positive")
    rows = tuple(intents)
    for intent in rows:
        intent.validate()
    if len({intent.intent_id for intent in rows}) != len(rows):
        raise ValueError("intent IDs must be unique")
    if rows != tuple(sorted(rows, key=lambda item: item.eligible_session)):
        raise ValueError("intents must be ordered by eligible session")

    cash = initial_cash
    positions: dict[str, int] = {}
    observations: list[ObservedExecution] = []
    for intent in rows:
        price = opening_prices.get(intent.eligible_session)
        if price is None or not math.isfinite(price) or price <= 0:
            observations.append(_rejected(intent, source))
            continue
        rate = intent.friction_bps / 10_000
        cost = intent.quantity * price * rate
        if intent.side is ExecutionSide.BUY:
            if positions.get(intent.symbol, 0) != 0:
                observations.append(_rejected(intent, source))
                continue
            total = intent.quantity * price + cost
            if total > cash:
                observations.append(_rejected(intent, source))
                continue
            cash -= total
            positions[intent.symbol] = intent.quantity
        else:
            if positions.get(intent.symbol, 0) != intent.quantity:
                observations.append(_rejected(intent, source))
                continue
            cash += intent.quantity * price - cost
            positions[intent.symbol] = 0
        observations.append(
            ObservedExecution(
                intent_id=intent.intent_id,
                status=ObservationStatus.FILLED,
                observed_session=intent.eligible_session,
                side=intent.side,
                quantity=intent.quantity,
                price=price,
                modeled_cost=cost,
                source=source,
            )
        )

    return ForwardSimulation(
        observations=tuple(observations),
        final_cash=cash,
        final_positions=tuple(sorted(positions.items())),
    )
