"""Explicit XNYS regular-session calendar and timezone normalization."""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

from tradinglab.constants import EXCHANGE_CALENDAR, TIMEZONE


def regular_sessions(start: date, end: date) -> pd.DatetimeIndex:
    """Return inclusive XNYS session labels at local New York midnight."""

    # The constructor's first/last labels are sessions, while callers may pass
    # weekend or holiday boundaries. A fixed pad keeps those requested dates
    # inside the explicitly materialized calendar without changing the query.
    calendar = xcals.get_calendar(
        EXCHANGE_CALENDAR,
        start=start - timedelta(days=7),
        end=end + timedelta(days=7),
        side="both",
    )
    labels = calendar.sessions_in_range(pd.Timestamp(start), pd.Timestamp(end))
    timezone = ZoneInfo(TIMEZONE)
    return pd.DatetimeIndex(
        [pd.Timestamp(label.date(), tz=timezone) for label in labels], name="Session"
    )


def normalize_daily_index(index: pd.Index) -> tuple[pd.DatetimeIndex, str]:
    """Normalize provider daily labels to unique New York session dates."""

    parsed = pd.DatetimeIndex(pd.to_datetime(index))
    source_timezone = str(parsed.tz) if parsed.tz is not None else "naive"
    timezone = ZoneInfo(TIMEZONE)
    if parsed.tz is not None:
        parsed = parsed.tz_convert(timezone)
    else:
        parsed = parsed.tz_localize(timezone)
    normalized = pd.DatetimeIndex(
        [pd.Timestamp(value.date(), tz=timezone) for value in parsed], name="Session"
    )
    return normalized, source_timezone
