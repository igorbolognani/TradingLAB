"""Explicit, transport-free contracts for the future paper phase.

Nothing in this package opens a network connection or submits an order.  The
objects describe decisions, observations, and provenance so a future paper
adapter can be reviewed independently before it is ever added.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any

PAPER_CONTRACT = "tradinglab/v0.3-paper-readiness/v1"


class PromotionState(StrEnum):
    """Human-controlled lifecycle for a research candidate."""

    RESEARCH = "research"
    CANDIDATE = "candidate"
    PAPER_APPROVED = "paper-approved"
    DISABLED = "disabled"


class ExecutionSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class ObservationStatus(StrEnum):
    FILLED = "filled"
    PARTIAL = "partial"
    REJECTED = "rejected"
    CANCELED = "canceled"


def _canonical_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat()


def _finite_positive(value: float, field_name: str) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field_name} must be finite and positive")


@dataclass(frozen=True, slots=True)
class PaperManifest:
    """Evidence and safety gate for a future paper observation run."""

    strategy_id: str
    strategy_version: str
    experiment_id: str
    dataset_id: str
    dataset_manifest_hash: str
    spec_hash: str
    v02_comparison_report_hash: str
    state: PromotionState
    holdout_seen: bool
    approved_by: str | None = None
    approved_at: datetime | None = None
    paper_session_limit: int = 60
    order_submission_allowed: bool = False
    live_trading_allowed: bool = False
    disabled_reason: str | None = None
    contract: str = PAPER_CONTRACT

    def validate(self) -> None:
        """Validate provenance and ensure this manifest cannot enable trading."""

        if self.contract != PAPER_CONTRACT:
            raise ValueError(f"unsupported paper contract: {self.contract}")
        for field_name in (
            "strategy_id",
            "strategy_version",
            "experiment_id",
            "dataset_id",
            "dataset_manifest_hash",
            "spec_hash",
            "v02_comparison_report_hash",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} is required")
        if self.paper_session_limit < 1:
            raise ValueError("paper_session_limit must be positive")
        if self.order_submission_allowed or self.live_trading_allowed:
            raise ValueError("V0.3 has no order-submission or live capability")
        if self.state is PromotionState.PAPER_APPROVED:
            if not self.holdout_seen:
                raise ValueError("the already-seen holdout must be acknowledged")
            if not self.approved_by or self.approved_at is None:
                raise ValueError("paper approval requires a human and timestamp")
            _canonical_datetime(self.approved_at)
        if self.state is PromotionState.DISABLED and not self.disabled_reason:
            raise ValueError("disabled manifests require a reason")

    def canonical_payload(self) -> dict[str, Any]:
        """Return the stable payload used for the manifest fingerprint."""

        self.validate()
        return {
            "contract": self.contract,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "experiment_id": self.experiment_id,
            "dataset_id": self.dataset_id,
            "dataset_manifest_hash": self.dataset_manifest_hash,
            "spec_hash": self.spec_hash,
            "v02_comparison_report_hash": self.v02_comparison_report_hash,
            "state": self.state.value,
            "holdout_seen": self.holdout_seen,
            "approved_by": self.approved_by,
            "approved_at": _canonical_datetime(self.approved_at),
            "paper_session_limit": self.paper_session_limit,
            "order_submission_allowed": self.order_submission_allowed,
            "live_trading_allowed": self.live_trading_allowed,
            "disabled_reason": self.disabled_reason,
        }

    def fingerprint(self) -> str:
        payload = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class ExecutionIntent:
    """A local decision that is eligible for a future observed fill."""

    intent_id: str
    strategy_id: str
    strategy_version: str
    symbol: str
    decision_session: date
    eligible_session: date
    side: ExecutionSide
    quantity: int
    expected_open: float
    friction_bps: float
    manifest_fingerprint: str

    def validate(self) -> None:
        if not self.intent_id or not self.strategy_id or not self.strategy_version:
            raise ValueError("intent identity fields are required")
        if not self.symbol:
            raise ValueError("symbol is required")
        if self.eligible_session <= self.decision_session:
            raise ValueError("execution must be after the decision session")
        if self.quantity < 1:
            raise ValueError("quantity must be a positive integer")
        _finite_positive(self.expected_open, "expected_open")
        if not math.isfinite(self.friction_bps) or self.friction_bps < 0:
            raise ValueError("friction_bps must be finite and non-negative")
        if len(self.manifest_fingerprint) != 64:
            raise ValueError("manifest_fingerprint must be a SHA-256 hex digest")


@dataclass(frozen=True, slots=True)
class ObservedExecution:
    """A fill observation or explicit rejection, still without transport."""

    intent_id: str
    status: ObservationStatus
    observed_session: date | None
    side: ExecutionSide | None
    quantity: int
    price: float | None
    modeled_cost: float
    source: str

    def validate(self) -> None:
        if not self.intent_id or not self.source:
            raise ValueError("observation identity and source are required")
        if self.quantity < 0:
            raise ValueError("observed quantity cannot be negative")
        if not math.isfinite(self.modeled_cost) or self.modeled_cost < 0:
            raise ValueError("modeled_cost must be finite and non-negative")
        if self.status is ObservationStatus.FILLED:
            if self.observed_session is None or self.side is None:
                raise ValueError("filled observations require session and side")
            if self.quantity < 1 or self.price is None:
                raise ValueError("filled observations require quantity and price")
            _finite_positive(self.price, "price")
        elif self.price is not None:
            _finite_positive(self.price, "price")
