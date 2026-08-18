from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from tradinglab.calendar import regular_sessions
from tradinglab.data_source import ProviderFrame, RetrievalRequest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC_DIR = PROJECT_ROOT / "strategy_specs"


def normalized_market_frame(
    sessions: pd.DatetimeIndex,
    *,
    closes: Sequence[float] | None = None,
    opens: Sequence[float] | None = None,
) -> pd.DataFrame:
    count = len(sessions)
    close_values = np.asarray(
        closes if closes is not None else np.linspace(100.0, 110.0, count),
        dtype=float,
    )
    open_values = np.asarray(opens if opens is not None else close_values, dtype=float)
    return pd.DataFrame(
        {
            "Open": open_values,
            "High": np.maximum(open_values, close_values) + 1.0,
            "Low": np.minimum(open_values, close_values) - 1.0,
            "Close": close_values,
            "Volume": np.full(count, 1_000, dtype=int),
            "AdjustmentFactor": np.ones(count),
        },
        index=sessions,
    )


def raw_provider_frame(
    start: date = date(2025, 1, 2),
    end: date = date(2025, 1, 10),
    *,
    omit: date | None = None,
) -> pd.DataFrame:
    sessions = regular_sessions(start, end)
    if omit is not None:
        sessions = sessions[sessions.date != omit]
    count = len(sessions)
    close = np.linspace(100.0, 106.0, count)
    open_ = close - 0.5
    factor = np.linspace(0.5, 1.0, count)
    dividends = np.zeros(count)
    splits = np.zeros(count)
    if count > 2:
        dividends[1] = 0.25
        splits[2] = 2.0
    return pd.DataFrame(
        {
            "Open": open_,
            "High": close + 1.0,
            "Low": open_ - 1.0,
            "Close": close,
            "Adj Close": close * factor,
            "Volume": np.arange(count, dtype=int) + 10_000,
            "Dividends": dividends,
            "Stock Splits": splits,
            "Capital Gains": np.zeros(count),
        },
        index=sessions,
    )


class StaticSource:
    provider = "fixture-provider"

    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame

    def fetch(self, symbol: str, request: RetrievalRequest) -> ProviderFrame:
        return ProviderFrame(
            symbol=symbol,
            frame=self.frame.copy(deep=True),
            provider=self.provider,
            provider_version="1.0-test",
            exact_query_arguments={
                "start": request.start.isoformat(),
                "end": request.end_exclusive.isoformat(),
                "interval": "1d",
                "auto_adjust": False,
                "actions": True,
                "prepost": False,
                "repair": False,
                "back_adjust": False,
                "keepna": True,
                "rounding": False,
                "timeout": 30,
                "raise_errors": True,
                "group_by": None,
                "multi_level_index": None,
                "threads": None,
                "ignore_tz": None,
                "timezone_behavior": "fixture preserves timezone",
                "missing_row_behavior": "no fill or drop",
            },
        )


@pytest.fixture
def spec_dir() -> Path:
    return SPEC_DIR


@pytest.fixture
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def fixture_request() -> RetrievalRequest:
    return RetrievalRequest(
        symbols=("SPY",),
        start=date(2025, 1, 2),
        end_exclusive=date(2025, 1, 11),
    )


@pytest.fixture
def static_source() -> StaticSource:
    return StaticSource(raw_provider_frame())


def assert_jsonable(value: Any) -> None:
    import json

    json.dumps(value, allow_nan=False)
