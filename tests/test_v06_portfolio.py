from datetime import date, timedelta

import pandas as pd
import pytest
from conftest import normalized_market_frame

from v0_6_portfolio.contract import PortfolioBar
from v0_6_portfolio.replay import build_trend_decisions, replay_portfolio
from v0_6_portfolio.service import run_trend_portfolio


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
    result = replay_portfolio(
        rows,
        decisions,
        friction_bps=0,
        evaluation_start=date(2020, 1, 3),
        evaluation_end=date(2020, 1, 5),
    )
    assert result.equity
    assert result.metrics["final_equity"] is not None
    assert result.metrics["final_equity"] > 100_000
    assert result.equity[0].session == date(2020, 1, 3)
    assert result.metrics["number_of_rebalances"] == 2
    assert result.equity[-1].positions
    assert result.metrics["Sharpe"] is not None
    assert result.metrics["gross_to_net_cost_drag"] == 0


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


def test_portfolio_rejects_missing_evaluation_sessions() -> None:
    rows = {"SPY": _bars("SPY", [100, 101, 102, 103])}
    with pytest.raises(ValueError, match="evaluation_start"):
        replay_portfolio(
            rows,
            (),
            evaluation_start=date(2020, 1, 10),
            evaluation_end=date(2020, 1, 11),
        )


def test_service_uses_full_history_for_warmup_but_starts_fresh_at_split() -> None:
    sessions = pd.date_range("2005-01-03", periods=260, freq="B")
    frames = {
        symbol: normalized_market_frame(
            sessions,
            closes=[100 + index * 0.1 for index in range(len(sessions))],
        )
        for symbol in ("SPY", "IWM", "EFA", "TLT", "GLD")
    }
    run = run_trend_portfolio(
        frames,
        evaluation_start=date(2005, 10, 1),
        evaluation_end=date(2005, 12, 30),
        friction_bps=0,
    )
    assert run.result.equity[0].session >= date(2005, 10, 1)
    assert run.result.equity[0].cash == pytest.approx(100_000)
    assert run.decisions
