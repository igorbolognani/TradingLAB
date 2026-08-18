"""Closed V0.1 constants shared by the research pipeline."""

from dataclasses import dataclass
from datetime import date

ASSETS: tuple[str, ...] = ("SPY", "IWM", "EFA", "TLT", "GLD")
TIMEZONE = "America/New_York"
EXCHANGE_CALENDAR = "XNYS"
REQUESTED_START = date(2005, 1, 1)
REQUESTED_END_EXCLUSIVE = date(2026, 1, 1)
INITIAL_CASH = 100_000.0
ANNUALIZATION_SESSIONS = 252
RISK_FREE_RATE = 0.0
PRIMARY_FRICTION_BPS = 5
FRICTION_SENSITIVITIES: tuple[int, ...] = (0, 5, 10, 25)
PRICE_BASIS_ID = "yahoo_total_return_adjusted_ohlc_v1"
NORMALIZATION_VERSION = "ohlc_total_return_v1"
NORMALIZATION_FORMULA = (
    "factor_t = Adj Close_t / raw Close_t; normalized OHLC_t = raw OHLC_t * "
    "factor_t; Volume preserved; dividends not separately credited"
)


@dataclass(frozen=True)
class TemporalSplit:
    """Inclusive evaluation boundary with an independent initial account."""

    key: str
    label: str
    start: date
    end: date
    is_holdout: bool = False


TEMPORAL_SPLITS: dict[str, TemporalSplit] = {
    "development": TemporalSplit(
        "development", "Development", date(2007, 1, 1), date(2014, 12, 31)
    ),
    "validation_oos": TemporalSplit(
        "validation_oos", "Validation OOS", date(2015, 1, 1), date(2019, 12, 31)
    ),
    "project_holdout": TemporalSplit(
        "project_holdout",
        "Project Holdout",
        date(2020, 1, 1),
        date(2025, 12, 31),
        is_holdout=True,
    ),
}

CANONICAL_STRATEGIES: tuple[str, ...] = (
    "CASH_0_V1",
    "BUY_HOLD_V1",
    "TREND_SMA200_V1",
    "MEANREV_Z20_V1",
)
