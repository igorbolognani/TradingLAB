"""LEAN custom data type for the frozen normalized daily-bar contract."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from QuantConnect import Globals, SubscriptionTransportMedium
from QuantConnect.Data import (
    BaseData,
    FileFormat,
    SubscriptionDataConfig,
    SubscriptionDataSource,
)
from QuantConnect.Python import PythonData


class NormalizedDailyBar(PythonData):
    """Read only locally prepared normalized OHLC data.

    Raw Yahoo rows and corporate actions are intentionally not exposed to the
    LEAN algorithm.  The input boundary is the normalized V0.1 research basis.
    """

    def get_source(
        self,
        config: SubscriptionDataConfig,
        date: datetime,
        is_live: bool,
    ) -> SubscriptionDataSource:
        asset = str(config.symbol.value)
        path = os.path.join(Globals.data_folder, "v0_2_normalized", f"{asset}.csv")
        return SubscriptionDataSource(
            path, SubscriptionTransportMedium.LOCAL_FILE, FileFormat.CSV
        )

    def reader(
        self,
        config: SubscriptionDataConfig,
        line: str,
        date: datetime,
        is_live: bool,
    ) -> BaseData | None:
        if not line.strip() or line.startswith("date,"):
            return None
        fields = line.split(",")
        if len(fields) != 6:
            return None
        try:
            bar = NormalizedDailyBar()
            bar.symbol = config.symbol
            bar.time = datetime.strptime(fields[0], "%Y-%m-%d")
            bar.end_time = bar.time + timedelta(days=1)
            bar.value = float(fields[4])
            bar["open"] = float(fields[1])
            bar["high"] = float(fields[2])
            bar["low"] = float(fields[3])
            bar["close"] = float(fields[4])
            bar["volume"] = float(fields[5])
            return bar
        except (TypeError, ValueError):
            return None
