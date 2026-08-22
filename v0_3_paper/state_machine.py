"""Human-gated promotion state transitions for paper readiness."""

from __future__ import annotations

from v0_3_paper.contract import PaperManifest, PromotionState

_TRANSITIONS: dict[PromotionState, frozenset[PromotionState]] = {
    PromotionState.RESEARCH: frozenset(
        {PromotionState.CANDIDATE, PromotionState.DISABLED}
    ),
    PromotionState.CANDIDATE: frozenset(
        {PromotionState.PAPER_APPROVED, PromotionState.DISABLED}
    ),
    PromotionState.PAPER_APPROVED: frozenset({PromotionState.DISABLED}),
    PromotionState.DISABLED: frozenset(),
}


def transition(
    current: PromotionState,
    target: PromotionState,
    *,
    human_approval: bool = False,
    evidence_complete: bool = False,
) -> PromotionState:
    """Return an explicitly requested state or reject the transition.

    This function does not persist a state, contact a broker, or infer an
    approval from metrics.  The caller must supply both human approval and
    complete evidence for the only consequential transition.
    """

    if target not in _TRANSITIONS[current]:
        raise ValueError(f"invalid promotion transition: {current} -> {target}")
    if target is PromotionState.PAPER_APPROVED and not (
        human_approval and evidence_complete
    ):
        raise PermissionError(
            "paper approval requires explicit human approval and complete evidence"
        )
    return target


def require_paper_ready(manifest: PaperManifest) -> None:
    """Validate that a manifest is approved for observation only."""

    manifest.validate()
    if manifest.state is not PromotionState.PAPER_APPROVED:
        raise PermissionError("manifest is not human-approved for paper observation")
