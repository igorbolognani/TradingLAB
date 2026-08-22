"""Frozen V0.2 comparison contract.

This module deliberately contains no imports from ``tradinglab``.  V0.2 is a
second implementation of the V0.1 behavior, not a wrapper around it.
"""

from __future__ import annotations

from datetime import date

ASSETS = ("SPY", "IWM", "EFA", "TLT", "GLD")
SPLITS: dict[str, tuple[date, date]] = {
    "development": (date(2007, 1, 1), date(2014, 12, 31)),
    "validation_oos": (date(2015, 1, 1), date(2019, 12, 31)),
    "project_holdout": (date(2020, 1, 1), date(2025, 12, 31)),
}
STRATEGIES = ("CASH_0_V1", "BUY_HOLD_V1", "TREND_SMA200_V1", "MEANREV_Z20_V1")
PRIMARY_PARAMETERS: dict[str, dict[str, float | int]] = {
    "CASH_0_V1": {},
    "BUY_HOLD_V1": {},
    "TREND_SMA200_V1": {"sma": 200},
    "MEANREV_Z20_V1": {
        "lookback": 20,
        "entry_z": -2.0,
        "exit_z": 0.0,
        "max_hold": 10,
    },
}
INITIAL_CASH = 100_000.0
ANNUALIZATION_SESSIONS = 252
RISK_FREE_RATE = 0.0
DEFAULT_FRICTION_BPS = 5

# V0.2 uses explicit tolerances instead of an unqualified "same result" claim.
METRIC_TOLERANCES = {
    "total_return": 1e-9,
    "CAGR": 1e-9,
    "annualized_volatility": 1e-9,
    "Sharpe": 1e-9,
    "max_drawdown": 1e-9,
    "exposure": 1e-12,
    "turnover": 1e-8,
    "number_of_trades": 0.0,
    "modeled_costs": 1e-6,
    "gross_to_net_cost_drag": 1e-9,
}
