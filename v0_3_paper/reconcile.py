"""Reconcile local intents with observed fills without hiding discrepancies."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from v0_3_paper.contract import ExecutionIntent, ObservationStatus, ObservedExecution


class ReconciliationStatus(StrEnum):
    MATCHED = "matched"
    MISSING = "missing"
    MISMATCH = "mismatch"
    DUPLICATE = "duplicate"
    UNEXPECTED = "unexpected"


@dataclass(frozen=True, slots=True)
class ReconciliationItem:
    intent_id: str
    status: ReconciliationStatus
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    items: tuple[ReconciliationItem, ...]

    @property
    def passed(self) -> bool:
        return all(item.status is ReconciliationStatus.MATCHED for item in self.items)


def reconcile(
    intents: tuple[ExecutionIntent, ...] | list[ExecutionIntent],
    observations: tuple[ObservedExecution, ...] | list[ObservedExecution],
    *,
    price_tolerance: float = 1e-8,
) -> ReconciliationReport:
    """Compare identity, timing, side, size, and observed price.

    Unexpected, missing, rejected, and duplicate records remain visible in the
    report.  A future external adapter can choose a different explicit price
    tolerance without changing the accounting contract.
    """

    if not math.isfinite(price_tolerance) or price_tolerance < 0:
        raise ValueError("price_tolerance must be finite and non-negative")
    intent_counts = Counter(intent.intent_id for intent in intents)
    intent_by_id = {intent.intent_id: intent for intent in intents}
    observed_by_id: dict[str, list[ObservedExecution]] = {}
    for observation in observations:
        observation.validate()
        observed_by_id.setdefault(observation.intent_id, []).append(observation)

    items: list[ReconciliationItem] = []
    for intent in intents:
        intent.validate()
        if intent_counts[intent.intent_id] > 1:
            items.append(
                ReconciliationItem(
                    intent.intent_id,
                    ReconciliationStatus.DUPLICATE,
                    ("more than one intent exists with this ID",),
                )
            )
            continue
        matches = observed_by_id.get(intent.intent_id, [])
        if not matches:
            items.append(
                ReconciliationItem(
                    intent.intent_id,
                    ReconciliationStatus.MISSING,
                    ("no observation exists for the intent",),
                )
            )
            continue
        if len(matches) > 1:
            items.append(
                ReconciliationItem(
                    intent.intent_id,
                    ReconciliationStatus.DUPLICATE,
                    ("more than one observation exists for the intent",),
                )
            )
            continue
        observation = matches[0]
        reasons: list[str] = []
        if observation.status is not ObservationStatus.FILLED:
            reasons.append(f"observation status is {observation.status.value}")
        if observation.observed_session != intent.eligible_session:
            reasons.append("observed session differs from eligible session")
        if observation.side is not intent.side:
            reasons.append("observed side differs from intent side")
        if observation.quantity != intent.quantity:
            reasons.append("observed quantity differs from intent quantity")
        if observation.price is None or not math.isclose(
            observation.price,
            intent.expected_open,
            rel_tol=0.0,
            abs_tol=price_tolerance,
        ):
            reasons.append("observed price differs from expected open")
        items.append(
            ReconciliationItem(
                intent.intent_id,
                (
                    ReconciliationStatus.MISMATCH
                    if reasons
                    else ReconciliationStatus.MATCHED
                ),
                tuple(reasons),
            )
        )

    for observation_id in sorted(set(observed_by_id) - set(intent_by_id)):
        items.append(
            ReconciliationItem(
                observation_id,
                ReconciliationStatus.UNEXPECTED,
                ("observation has no matching intent",),
            )
        )
    return ReconciliationReport(tuple(items))
