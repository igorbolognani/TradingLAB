"""QuantConnect LEAN implementation of the six-point V0.2 contract."""

# LEAN injects AlgorithmImports at runtime; this file is linted separately
# from the V0.1 Python package and is syntax-checked in the local suite.
# ruff: noqa

from __future__ import annotations

import json
import math
import os
from csv import DictReader
from datetime import date, timedelta

from AlgorithmImports import *

from algorithms.normalized_daily import NormalizedDailyBar


SPLITS = {
    "development": (date(2007, 1, 1), date(2014, 12, 31)),
    "validation_oos": (date(2015, 1, 1), date(2019, 12, 31)),
    "project_holdout": (date(2020, 1, 1), date(2025, 12, 31)),
}


class ModeledFrictionFeeModel(FeeModel):
    def __init__(self, friction_bps: float, opens: dict[date, float]) -> None:
        self.friction_bps = friction_bps
        self.opens = opens

    def get_order_fee(self, parameters: OrderFeeParameters) -> OrderFee:
        price = parameters.security.price
        try:
            price = self.opens.get(date.fromisoformat(str(parameters.order.tag)), price)
        except ValueError:
            pass
        notional = abs(float(parameters.order.quantity) * float(price))
        return OrderFee(CashAmount(notional * self.friction_bps / 10000, "USD"))


class NormalizedOpenFillModel(FillModel):
    """Fill MOO orders from the normalized bar's explicit open field."""

    def __init__(self, opens: dict[date, float]) -> None:
        self.opens = opens

    @staticmethod
    def _create_order_event(asset: Security, order: Order) -> OrderEvent:
        utc_time = Extensions.convert_to_utc(asset.local_time, asset.exchange.time_zone)
        return OrderEvent(order, utc_time, OrderFee.ZERO)

    def market_on_open_fill(
        self, asset: Security, order: MarketOnOpenOrder
    ) -> OrderEvent:
        fill = self._create_order_event(asset, order)
        if order.status == OrderStatus.CANCELED:
            return fill
        try:
            price = self.opens.get(
                date.fromisoformat(str(order.tag)), float(asset.price)
            )
        except ValueError:
            price = float(asset.price)
        fill.status = OrderStatus.FILLED
        fill.fill_quantity = order.quantity
        fill.fill_price = price
        return fill


class TradingLabV02Algorithm(QCAlgorithm):
    """One explicit asset/split/configuration per LEAN backtest invocation."""

    def initialize(self) -> None:
        self.asset = self.get_parameter("asset") or "SPY"
        self.split = self.get_parameter("split") or "development"
        self.strategy_id = self.get_parameter("strategy_id") or "CASH_0_V1"
        self.friction_bps = float(self.get_parameter("friction_bps") or 5)
        self.start, self.end = SPLITS[self.split]
        self.lookback = {
            "TREND_SMA200_V1": 200,
            "MEANREV_Z20_V1": 20,
        }.get(self.strategy_id, 0)
        engine_start = self._engine_start_date()
        self.set_start_date(engine_start.year, engine_start.month, engine_start.day)
        self.set_end_date(self.end.year, self.end.month, self.end.day)
        self.set_cash(100000)
        self.set_time_zone(TimeZones.NEW_YORK)
        exchange_hours = (
            MarketHoursDatabase.from_data_folder()
            .get_entry("usa", self.asset, SecurityType.EQUITY)
            .exchange_hours
        )
        symbol_properties = SymbolProperties(
            "normalized daily", "USD", 1, 0.01, 1, self.asset
        )
        self.security = self.add_data(
            NormalizedDailyBar,
            self.asset,
            symbol_properties,
            exchange_hours,
            Resolution.DAILY,
        )
        self.opens_by_session = self._load_opens()
        self.security.set_fee_model(
            ModeledFrictionFeeModel(self.friction_bps, self.opens_by_session)
        )
        # LEAN's MOO pre-check cannot see the next custom-data open and would
        # reject a valid cash-sized order using the intervening close instead.
        self.security.set_buying_power_model(NullBuyingPowerModel())
        self.security.set_fill_model(NormalizedOpenFillModel(self.opens_by_session))
        self.symbol = self.security.symbol
        self.next_open_by_session = self._load_next_opens()
        self.closes: list[float] = []
        self.pending_action: str | None = None
        self.pending_reason: str | None = None
        self.pending_quantity = 0
        self.pending_fill_session: date | None = None
        self.pending_order_id: int | None = None
        self.entry_sessions = 0
        self.set_warm_up(self.lookback, Resolution.DAILY)
        self.schedule.on(
            self.date_rules.every_day(self.symbol),
            self.time_rules.before_market_open(self.symbol, 1),
            self._submit_pending_order,
        )

    def on_data(self, data: Slice) -> None:
        if not data.contains_key(self.symbol):
            return
        bar = data[self.symbol]
        close = float(bar.value)
        self.closes.append(close)
        if self.is_warming_up:
            return

        invested = self.portfolio[self.symbol].quantity > 0
        if invested:
            self.entry_sessions += 1
        action, reason, indicator = self._decision(close, invested)
        if action is None or self.pending_action is not None:
            return
        session = bar.time.date()
        if session < self.first_decision_session:
            return
        if action == "enter":
            rate = self.friction_bps / 10000
            open_price = self.next_open_by_session.get(session)
            if open_price is None:
                return
            quantity = math.floor(self.portfolio.cash / (open_price * (1 + rate)))
            if quantity <= 0:
                return
            self.pending_quantity = quantity
            self.pending_fill_session = self._next_session(session)
        else:
            self.pending_quantity = -self.portfolio[self.symbol].quantity
            if self.pending_quantity == 0:
                return
            self.pending_fill_session = self._next_session(session)
        self.pending_action = action
        self.pending_reason = reason
        self.debug(
            json.dumps(
                {
                    "event": "signal",
                    "session": str(session),
                    "action": action,
                    "reason": reason,
                    "indicator": indicator,
                },
                sort_keys=True,
            )
        )

    def on_order_event(self, order_event: OrderEvent) -> None:
        if order_event.status != OrderStatus.FILLED:
            return
        if self.pending_action == "enter":
            # The fill session itself is counted by the next daily data event,
            # matching the canonical replay's session-one convention.
            self.entry_sessions = 0
        elif self.pending_action == "exit":
            self.entry_sessions = 0
        self.debug(
            json.dumps(
                {
                    "event": "fill",
                    "fill_session": self.pending_fill_session.isoformat()
                    if self.pending_fill_session is not None
                    else None,
                    "session": str(self.time.date()),
                    "quantity": order_event.fill_quantity,
                    "price": order_event.fill_price,
                    "reason": self.pending_reason,
                },
                sort_keys=True,
            )
        )
        self.pending_action = None
        self.pending_reason = None
        self.pending_quantity = 0
        self.pending_fill_session = None
        self.pending_order_id = None

    def _submit_pending_order(self) -> None:
        if self.pending_action is None or self.pending_order_id is not None:
            return
        tag = (
            self.pending_fill_session.isoformat()
            if self.pending_fill_session is not None
            else ""
        )
        ticket = self.market_on_open_order(self.symbol, self.pending_quantity, tag=tag)
        if ticket.status == OrderStatus.INVALID:
            self.debug(
                json.dumps(
                    {
                        "event": "order_invalid",
                        "message": ticket.order_settlement_status,
                        "reason": self.pending_reason,
                    },
                    sort_keys=True,
                )
            )
            self.pending_action = None
            self.pending_reason = None
            self.pending_quantity = 0
            self.pending_fill_session = None
            return
        self.pending_order_id = ticket.order_id

    def _decision(
        self, close: float, invested: bool
    ) -> tuple[str | None, str | None, float | None]:
        if self.strategy_id == "CASH_0_V1":
            return None, None, None
        if self.strategy_id == "BUY_HOLD_V1":
            return (
                ("enter", "first_eligible_open", None)
                if not invested
                else (None, None, None)
            )
        if self.strategy_id == "TREND_SMA200_V1":
            if len(self.closes) < 200:
                return None, None, None
            sma = sum(self.closes[-200:]) / 200
            if close > sma and not invested:
                return "enter", "close_above_sma", sma
            if close <= sma and invested:
                return "exit", "close_at_or_below_sma", sma
            return None, None, sma
        if self.strategy_id == "MEANREV_Z20_V1":
            if len(self.closes) < 20:
                return None, None, None
            sample = self.closes[-20:]
            average = sum(sample) / 20
            deviation = math.sqrt(sum((value - average) ** 2 for value in sample) / 20)
            zscore = None if deviation == 0 else (close - average) / deviation
            if not invested and zscore is not None and zscore <= -2:
                return "enter", "zscore_entry", zscore
            if invested and zscore is not None and zscore >= 0:
                return "exit", "zscore_exit", zscore
            if invested and self.entry_sessions >= 10:
                return "exit", "max_hold_exit", zscore
            return None, None, zscore
        raise ValueError(f"unknown strategy: {self.strategy_id}")

    def _load_next_opens(self) -> dict[date, float]:
        path = os.path.join(Globals.data_folder, "v0_2_normalized", f"{self.asset}.csv")
        with open(path, newline="") as handle:
            rows = list(DictReader(handle))
        return {
            date.fromisoformat(previous["date"]): float(current["open"])
            for previous, current in zip(rows, rows[1:])
        }

    def _load_opens(self) -> dict[date, float]:
        path = os.path.join(Globals.data_folder, "v0_2_normalized", f"{self.asset}.csv")
        with open(path, newline="") as handle:
            return {
                date.fromisoformat(row["date"]): float(row["open"])
                for row in DictReader(handle)
            }

    def _engine_start_date(self) -> date:
        path = os.path.join(Globals.data_folder, "v0_2_normalized", f"{self.asset}.csv")
        with open(path, newline="") as handle:
            sessions = [date.fromisoformat(row["date"]) for row in DictReader(handle)]
        split_index = next(
            index for index, session in enumerate(sessions) if session >= self.start
        )
        self.first_decision_session = sessions[max(0, split_index - 1)]
        if self.lookback == 0:
            return self.first_decision_session + timedelta(days=1)
        return sessions[max(0, split_index - self.lookback)]

    def _next_session(self, session: date) -> date | None:
        for candidate in self.next_open_by_session:
            if candidate > session:
                return candidate
        return None
