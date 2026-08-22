from datetime import date, timedelta

import pytest

from v0_6_portfolio.contract import PortfolioBar
from v0_6_portfolio.replay import build_trend_decisions, replay_portfolio


def _bars(symbol: str, values: list[float]) -> list[PortfolioBar]:
    return [
        PortfolioBar(
            session=date(2020, 1, 1) + timedelta(days=index),
            symbol=symbol,
            open=value,
            close=value,
        )
        for index, value in enumerate(values)
    ]


def test_portfolio_decisions_use_next_session_and_share_cash() -> None:
    rows = {
        "SPY": _bars("SPY", [100, 101, 102, 103, 104, 105]),
        "TLT": _bars("TLT", [100, 100, 100, 100, 100, 100]),
    }
    decisions = build_trend_decisions(rows, sma_window=2, rebalance_every=2)
    assert decisions[0].decision_session < decisions[0].execution_session
    result = replay_portfolio(rows, decisions, friction_bps=0)
    assert result.equity
    assert result.metrics["final_equity"] is not None
    assert result.metrics["final_equity"] > 100_000


def test_inverse_vol_is_explicit_and_no_unknown_symbols_are_allowed() -> None:
    rows = {
        "SPY": _bars("SPY", [100, 101, 102, 103, 104, 105]),
        "TLT": _bars("TLT", [100, 99, 101, 98, 102, 97]),
    }
    decisions = build_trend_decisions(rows, sma_window=2, rebalance_every=2)
    result = replay_portfolio(
        rows,
        decisions,
        allocation_method="inverse_vol",
        friction_bps=0,
        volatility_lookback=2,
    )
    assert result.allocation_method == "inverse_vol"
    assert result.metrics["modeled_costs"] == 0

    bad = decisions[0].__class__(
        decisions[0].decision_session,
        decisions[0].execution_session,
        ("UNKNOWN",),
    )
    with pytest.raises(ValueError, match="unknown symbol"):
        replay_portfolio(rows, [bad])
