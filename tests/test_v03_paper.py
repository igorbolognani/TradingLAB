from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from v0_3_paper.contract import (
    ExecutionIntent,
    ExecutionSide,
    ObservationStatus,
    PaperManifest,
    PromotionState,
)
from v0_3_paper.forward_sim import simulate_forward
from v0_3_paper.reconcile import ReconciliationStatus, reconcile
from v0_3_paper.state_machine import transition


def _manifest(state: PromotionState = PromotionState.CANDIDATE) -> PaperManifest:
    return PaperManifest(
        strategy_id="TREND_SMA200_V1",
        strategy_version="V1",
        experiment_id="exp_test",
        dataset_id="ds_test",
        dataset_manifest_hash="a" * 64,
        spec_hash="b" * 64,
        v02_comparison_report_hash="c" * 64,
        state=state,
        holdout_seen=True,
        approved_by=("human" if state is PromotionState.PAPER_APPROVED else None),
        approved_at=(
            datetime(2026, 8, 22, tzinfo=UTC)
            if state is PromotionState.PAPER_APPROVED
            else None
        ),
        disabled_reason=("test" if state is PromotionState.DISABLED else None),
    )


def _intent(
    intent_id: str,
    side: ExecutionSide,
    session: date,
    expected_open: float,
    quantity: int = 10,
) -> ExecutionIntent:
    return ExecutionIntent(
        intent_id=intent_id,
        strategy_id="TREND_SMA200_V1",
        strategy_version="V1",
        symbol="SPY",
        decision_session=date(2026, 8, 21),
        eligible_session=session,
        side=side,
        quantity=quantity,
        expected_open=expected_open,
        friction_bps=5,
        manifest_fingerprint="d" * 64,
    )


def test_paper_approval_is_explicitly_human_gated() -> None:
    assert transition(PromotionState.RESEARCH, PromotionState.CANDIDATE)
    with pytest.raises(PermissionError):
        transition(PromotionState.CANDIDATE, PromotionState.PAPER_APPROVED)
    assert (
        transition(
            PromotionState.CANDIDATE,
            PromotionState.PAPER_APPROVED,
            human_approval=True,
            evidence_complete=True,
        )
        is PromotionState.PAPER_APPROVED
    )
    _manifest(PromotionState.PAPER_APPROVED).validate()


def test_manifest_never_allows_live_or_order_submission() -> None:
    manifest = _manifest()
    with pytest.raises(ValueError, match="no order-submission"):
        replace(manifest, order_submission_allowed=True).validate()


def test_forward_simulation_and_reconciliation_are_deterministic() -> None:
    buy = _intent("buy-1", ExecutionSide.BUY, date(2026, 8, 24), 100)
    sell = _intent("sell-1", ExecutionSide.SELL, date(2026, 8, 25), 105)
    run = simulate_forward(
        [buy, sell],
        opening_prices={date(2026, 8, 24): 100, date(2026, 8, 25): 105},
    )
    assert [item.status for item in run.observations] == [
        ObservationStatus.FILLED,
        ObservationStatus.FILLED,
    ]
    report = reconcile([buy, sell], list(run.observations))
    assert report.passed
    assert all(item.status is ReconciliationStatus.MATCHED for item in report.items)


def test_reconciliation_preserves_missing_observations() -> None:
    intent = _intent("missing", ExecutionSide.BUY, date(2026, 8, 24), 100)
    report = reconcile([intent], [])
    assert not report.passed
    assert report.items[0].status is ReconciliationStatus.MISSING


def test_reconciliation_preserves_duplicate_intents() -> None:
    intent = _intent("duplicate", ExecutionSide.BUY, date(2026, 8, 24), 100)
    report = reconcile([intent, intent], [])
    assert not report.passed
    assert all(item.status is ReconciliationStatus.DUPLICATE for item in report.items)
