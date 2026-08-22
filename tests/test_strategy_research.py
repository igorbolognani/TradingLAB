from datetime import date, timedelta

from v0_2_lean.core import Bar
from v0_2_lean.research_candidates import (
    CANDIDATE_IDS,
    replay_candidate,
)


def _bars(start: date, closes: list[float]) -> list[Bar]:
    return [
        Bar(day, value, value, value, value, 1)
        for day, value in (
            (start + timedelta(days=i), value) for i, value in enumerate(closes)
        )
    ]


def test_research_candidate_set_is_fixed_and_separate() -> None:
    assert CANDIDATE_IDS == (
        "TSMOM_12M_RESEARCH_V1",
        "TREND_BLEND_3_6_12_RESEARCH_V1",
        "TREND_GATED_MEANREV_RESEARCH_V1",
    )


def test_tsmom_candidate_uses_only_confirmed_close_and_next_session() -> None:
    bars = _bars(date(2006, 1, 1), [100 + index for index in range(800)])
    result = replay_candidate(
        bars,
        asset="SPY",
        split="development",
        strategy_id="TSMOM_12M_RESEARCH_V1",
    )
    assert result.signals
    assert result.signals[0].decision_session < result.signals[0].fill_session
    assert result.signals[0].reason == "positive_12m_momentum"


def test_trend_gated_mean_reversion_requires_both_components() -> None:
    bars = _bars(date(2006, 1, 1), [100.0] * 800)
    result = replay_candidate(
        bars,
        asset="SPY",
        split="development",
        strategy_id="TREND_GATED_MEANREV_RESEARCH_V1",
    )
    assert result.signals == ()
    assert result.fills == 0
