import math

import numpy as np
import pandas as pd
import pytest

from tradinglab.metrics import benchmark_deltas, canonical_metrics


def test_all_canonical_metrics_against_manual_equity_curve() -> None:
    equity = pd.DataFrame(
        {
            "net_equity": [100_000.0, 110_000.0, 99_000.0],
            "gross_equity": [100_010.0, 110_010.0, 99_020.0],
            "exposure_state": [0, 1, 1],
        }
    )
    trades = pd.DataFrame(
        {
            "lifecycle_id": [1, 1],
            "side": ["buy", "sell"],
            "fill_notional": [50_000.0, 55_000.0],
            "modeled_friction": [10.0, 10.0],
        }
    )
    result = canonical_metrics(equity, trades)
    returns = np.array([0.0, 0.1, -0.1])
    sample_std = np.std(returns, ddof=1)
    assert result["total_return"] == pytest.approx(-0.01)
    assert result["CAGR"] == pytest.approx(0.99 ** (252 / 3) - 1)
    assert result["annualized_volatility"] == pytest.approx(sample_std * math.sqrt(252))
    assert result["Sharpe"] == pytest.approx(
        np.mean(returns) / sample_std * math.sqrt(252)
    )
    assert result["max_drawdown"] == pytest.approx(-0.1)
    assert result["exposure"] == pytest.approx(2 / 3)
    assert result["turnover"] == pytest.approx(105_000 / equity["net_equity"].mean())
    assert result["number_of_trades"] == 1
    assert result["modeled_costs"] == 20
    assert result["gross_to_net_cost_drag"] == pytest.approx(0.0002)


def test_zero_volatility_and_insufficient_sample_are_never_infinite() -> None:
    empty_trades = pd.DataFrame(
        columns=["lifecycle_id", "side", "fill_notional", "modeled_friction"]
    )
    constant = pd.DataFrame(
        {
            "net_equity": [100_000.0, 100_000.0],
            "gross_equity": [100_000.0, 100_000.0],
            "exposure_state": [0, 0],
        }
    )
    result = canonical_metrics(constant, empty_trades)
    assert result["annualized_volatility"] == 0.0
    assert result["Sharpe"] is None
    single = canonical_metrics(constant.iloc[:1], empty_trades)
    assert single["annualized_volatility"] is None
    assert single["Sharpe"] is None


def test_buy_hold_deltas_include_drawdown_sign_convention() -> None:
    strategy = {"CAGR": 0.08, "Sharpe": 0.7, "max_drawdown": -0.2}
    benchmark = {"CAGR": 0.1, "Sharpe": 0.5, "max_drawdown": -0.3}
    assert benchmark_deltas(strategy, benchmark) == {
        "delta_CAGR_vs_buy_hold": -0.020000000000000004,
        "delta_Sharpe_vs_buy_hold": 0.19999999999999996,
        "delta_max_drawdown_vs_buy_hold": 0.09999999999999998,
    }
