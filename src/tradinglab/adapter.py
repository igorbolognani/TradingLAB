"""Backtesting.py adapter with authoritative V0.1 canonical ledgers."""

import math
import warnings
from dataclasses import dataclass
from typing import Any

import backtesting
import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy

from tradinglab.constants import INITIAL_CASH, TemporalSplit
from tradinglab.indicators import indicator_series
from tradinglab.specs import StrategySpec
from tradinglab.strategies import Decision, DecisionMachine

ENGINE_NAME = "Backtesting.py"
ENGINE_VERSION = backtesting.__version__


@dataclass(frozen=True)
class PendingOrder:
    decision: Decision
    decision_session: pd.Timestamp | None
    eligibility_session: pd.Timestamp
    signal_index: int


@dataclass(frozen=True)
class AdapterResult:
    """Canonical outputs plus extracted native-engine reference data."""

    trades: pd.DataFrame
    equity_curve: pd.DataFrame
    signals: pd.DataFrame
    engine_trades: pd.DataFrame
    engine_equity_curve: pd.DataFrame
    engine_configuration: dict[str, Any]
    terminal_position_quantity: int
    terminal_position_open: bool


def engine_configuration(friction_bps: int) -> dict[str, Any]:
    """Every material Backtesting.py execution option, with no hidden default."""

    return {
        "cash": INITIAL_CASH,
        "spread": 0.0,
        "commission": friction_bps / 10_000,
        "margin": 1.0,
        "trade_on_close": False,
        "hedging": False,
        "exclusive_orders": True,
        "finalize_trades": False,
        "integer_size": True,
        "terminal_handling": "mark_to_final_normalized_close_without_forced_exit",
    }


def _iso(session: pd.Timestamp | None) -> str | None:
    return session.date().isoformat() if session is not None else None


def _as_float(value: Any) -> float:
    return float(value)


def _as_timestamp(value: Any) -> pd.Timestamp:
    return pd.Timestamp(value)


def _index_location(index: pd.Index, value: pd.Timestamp) -> int:
    location = index.get_loc(value)
    if not isinstance(location, (int, np.integer)):
        raise ValueError("session index must be unique")
    return int(location)


class BacktestingPyAdapter:
    """Translate declared decisions into next-open fills and audit ledgers."""

    def run(
        self,
        *,
        data: pd.DataFrame,
        spec: StrategySpec,
        parameters: dict[str, float | int],
        split: TemporalSplit,
        friction_bps: int,
    ) -> AdapterResult:
        self._validate_input(data, spec, friction_bps)
        dates = pd.DatetimeIndex(data.index).date
        evaluation_mask = (dates >= split.start) & (dates <= split.end)
        evaluation = data.loc[evaluation_mask]
        if evaluation.empty:
            raise ValueError(f"no rows in evaluation split {split.key}")
        indicator = indicator_series(data["Close"], spec.strategy_id, parameters)
        machine = DecisionMachine(spec.strategy_id, parameters)

        cash = INITIAL_CASH
        gross_cash = INITIAL_CASH
        quantity = 0
        held_sessions = 0
        cumulative_costs = 0.0
        lifecycle = 0
        active_entry_row: int | None = None
        pending: PendingOrder | None = None
        trades: list[dict[str, Any]] = []
        signals: list[dict[str, Any]] = []
        equity_rows: list[dict[str, Any]] = []
        evaluation_index = pd.DatetimeIndex(evaluation.index)

        prior_rows = data.index[data.index < evaluation_index[0]]
        prior_session = pd.Timestamp(prior_rows[-1]) if len(prior_rows) else None

        def record_signal(
            decision: Decision,
            decision_session: pd.Timestamp | None,
            eligibility_session: pd.Timestamp,
            *,
            within_evaluation: bool,
        ) -> PendingOrder:
            signals.append(
                {
                    "decision_session": _iso(decision_session),
                    "order_eligibility_session": _iso(eligibility_session),
                    "action": decision.action,
                    "reason": decision.reason,
                    "indicator_value": decision.indicator_value,
                    "within_evaluation": within_evaluation,
                    "fill_session": None,
                    "fill_status": "pending"
                    if within_evaluation
                    else "outside_evaluation",
                }
            )
            return PendingOrder(
                decision=decision,
                decision_session=decision_session,
                eligibility_session=eligibility_session,
                signal_index=len(signals) - 1,
            )

        if spec.strategy_id == "BUY_HOLD_V1":
            pending = record_signal(
                Decision("enter", "first_eligible_open", None),
                prior_session,
                evaluation_index[0],
                within_evaluation=True,
            )
        elif prior_session is not None:
            prior_decision = machine.after_close(
                close=_as_float(data.loc[prior_session, "Close"]),
                indicator=float(indicator.loc[prior_session]),
                in_position=False,
                held_sessions=0,
            )
            if prior_decision is not None:
                pending = record_signal(
                    prior_decision,
                    prior_session,
                    evaluation_index[0],
                    within_evaluation=True,
                )

        friction_rate = friction_bps / 10_000
        for offset, (session_value, row) in enumerate(evaluation.iterrows()):
            session = _as_timestamp(session_value)
            open_price = _as_float(row["Open"])
            if pending is not None:
                if pending.eligibility_session != session:
                    raise AssertionError(
                        "pending order did not reach its declared session"
                    )
                signal_row = signals[pending.signal_index]
                if pending.decision.action == "enter" and quantity == 0:
                    estimated_cost = open_price * (1 + friction_rate)
                    fill_quantity = math.floor(cash / estimated_cost)
                    if fill_quantity < 1:
                        signal_row["fill_status"] = "skipped_insufficient_cash"
                    else:
                        notional = fill_quantity * open_price
                        cost = abs(notional) * friction_rate
                        next_cash = cash - notional - cost
                        if next_cash < -1e-8:
                            raise AssertionError(
                                "entry would spend more cash than available"
                            )
                        cash = max(0.0, next_cash)
                        gross_cash -= notional
                        cumulative_costs += cost
                        quantity = fill_quantity
                        held_sessions = 0
                        lifecycle += 1
                        trades.append(
                            {
                                "lifecycle_id": lifecycle,
                                "signal_session": _iso(pending.decision_session),
                                "order_eligibility_session": _iso(session),
                                "fill_session": _iso(session),
                                "side": "buy",
                                "quantity": fill_quantity,
                                "normalized_fill_price": open_price,
                                "fill_notional": notional,
                                "modeled_friction": cost,
                                "cash_impact": -(notional + cost),
                                "entry_reason": pending.decision.reason,
                                "exit_reason": None,
                                "held_session_count": 1,
                                "terminal_status": "open",
                            }
                        )
                        active_entry_row = len(trades) - 1
                        signal_row["fill_status"] = "filled"
                        signal_row["fill_session"] = _iso(session)
                elif pending.decision.action == "exit" and quantity > 0:
                    exit_quantity = quantity
                    notional = exit_quantity * open_price
                    cost = abs(notional) * friction_rate
                    cash += notional - cost
                    gross_cash += notional
                    cumulative_costs += cost
                    trades.append(
                        {
                            "lifecycle_id": lifecycle,
                            "signal_session": _iso(pending.decision_session),
                            "order_eligibility_session": _iso(session),
                            "fill_session": _iso(session),
                            "side": "sell",
                            "quantity": exit_quantity,
                            "normalized_fill_price": open_price,
                            "fill_notional": notional,
                            "modeled_friction": cost,
                            "cash_impact": notional - cost,
                            "entry_reason": None,
                            "exit_reason": pending.decision.reason,
                            "held_session_count": held_sessions,
                            "terminal_status": "closed",
                        }
                    )
                    if active_entry_row is None:
                        raise AssertionError(
                            "exit without an auditable entry lifecycle"
                        )
                    trades[active_entry_row]["terminal_status"] = "closed"
                    active_entry_row = None
                    quantity = 0
                    held_sessions = 0
                    signal_row["fill_status"] = "filled"
                    signal_row["fill_session"] = _iso(session)
                else:
                    raise AssertionError("duplicate or incompatible pending order")
                pending = None

            if quantity > 0:
                held_sessions += 1
                if active_entry_row is not None:
                    trades[active_entry_row]["held_session_count"] = held_sessions

            close_price = _as_float(row["Close"])
            gross_equity = gross_cash + quantity * close_price
            net_equity = cash + quantity * close_price
            if not math.isclose(
                gross_equity - cumulative_costs,
                net_equity,
                rel_tol=1e-10,
                abs_tol=1e-7,
            ):
                raise AssertionError("gross-to-net ledger does not reconcile")
            equity_rows.append(
                {
                    "session": _iso(session),
                    "cash": cash,
                    "position_quantity": quantity,
                    "normalized_close": close_price,
                    "gross_equity": gross_equity,
                    "cumulative_modeled_costs": cumulative_costs,
                    "net_equity": net_equity,
                    "exposure_state": int(quantity > 0),
                }
            )

            decision = machine.after_close(
                close=close_price,
                indicator=float(indicator.loc[session]),
                in_position=quantity > 0,
                held_sessions=held_sessions,
            )
            if decision is not None:
                all_position = _index_location(data.index, session)
                next_position = all_position + 1
                if next_position >= len(data.index):
                    continue
                eligibility = pd.Timestamp(data.index[next_position])
                within = offset + 1 < len(evaluation_index)
                candidate = record_signal(
                    decision, session, eligibility, within_evaluation=within
                )
                if within:
                    if eligibility != evaluation_index[offset + 1]:
                        raise ValueError("evaluation data has a missing next session")
                    pending = candidate

        trade_columns = [
            "lifecycle_id",
            "signal_session",
            "order_eligibility_session",
            "fill_session",
            "side",
            "quantity",
            "normalized_fill_price",
            "fill_notional",
            "modeled_friction",
            "cash_impact",
            "entry_reason",
            "exit_reason",
            "held_session_count",
            "terminal_status",
        ]
        signal_columns = [
            "decision_session",
            "order_eligibility_session",
            "action",
            "reason",
            "indicator_value",
            "within_evaluation",
            "fill_session",
            "fill_status",
        ]
        trade_frame = pd.DataFrame(trades, columns=trade_columns)
        signal_frame = pd.DataFrame(signals, columns=signal_columns)
        equity_frame = pd.DataFrame(equity_rows)
        native_trades, native_equity = self._run_engine_reference(
            data=data,
            evaluation=evaluation,
            canonical_trades=trade_frame,
            friction_bps=friction_bps,
        )
        return AdapterResult(
            trades=trade_frame,
            equity_curve=equity_frame,
            signals=signal_frame,
            engine_trades=native_trades,
            engine_equity_curve=native_equity,
            engine_configuration=engine_configuration(friction_bps),
            terminal_position_quantity=quantity,
            terminal_position_open=quantity > 0,
        )

    @staticmethod
    def _validate_input(
        data: pd.DataFrame, spec: StrategySpec, friction_bps: int
    ) -> None:
        if friction_bps not in {0, 5, 10, 25}:
            raise ValueError("friction must be a predeclared V0.1 scenario")
        required = {"Open", "High", "Low", "Close", "Volume"}
        if not required.issubset(data.columns):
            raise ValueError("normalized data does not satisfy OHLCV contract")
        if data.index.has_duplicates or not data.index.is_monotonic_increasing:
            raise ValueError("normalized data index must be chronological and unique")
        if (data[["Open", "High", "Low", "Close"]] <= 0).any().any():
            raise ValueError("execution prices must be strictly positive")
        if not spec.risk_constraints.long_only or spec.risk_constraints.leverage != 1:
            raise ValueError("adapter accepts only the V0.1 long/cash risk contract")

    @staticmethod
    def _run_engine_reference(
        *,
        data: pd.DataFrame,
        evaluation: pd.DataFrame,
        canonical_trades: pd.DataFrame,
        friction_bps: int,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Replay canonical decisions through installed Backtesting.py semantics."""

        first_location = _index_location(data.index, pd.Timestamp(evaluation.index[0]))
        start = max(0, first_location - 2)
        last_location = _index_location(data.index, pd.Timestamp(evaluation.index[-1]))
        engine_data = data.iloc[start : last_location + 1]
        engine_data = engine_data.loc[:, ["Open", "High", "Low", "Close", "Volume"]]
        schedule: dict[str, list[tuple[str, int]]] = {}
        for row in canonical_trades.to_dict(orient="records"):
            signal_session = row["signal_session"]
            if signal_session is None:
                continue
            schedule.setdefault(str(signal_session), []).append(
                (str(row["side"]), int(row["quantity"]))
            )

        class CanonicalReplay(Strategy):  # type: ignore[misc]
            def init(self) -> None:
                pass

            def next(self) -> None:
                key = pd.Timestamp(self.data.index[-1]).date().isoformat()
                for side, fill_quantity in schedule.get(key, []):
                    if side == "buy":
                        self.buy(size=fill_quantity, tag="canonical_replay")
                    elif self.position:
                        self.position.close()

        configuration = engine_configuration(friction_bps)
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message="Some prices are larger than initial cash value.*"
            )
            warnings.filterwarnings(
                "ignore", message="Some trades remain open at the end of backtest.*"
            )
            backtest = Backtest(
                engine_data,
                CanonicalReplay,
                cash=float(configuration["cash"]),
                spread=float(configuration["spread"]),
                commission=float(configuration["commission"]),
                margin=float(configuration["margin"]),
                trade_on_close=bool(configuration["trade_on_close"]),
                hedging=bool(configuration["hedging"]),
                exclusive_orders=bool(configuration["exclusive_orders"]),
                finalize_trades=bool(configuration["finalize_trades"]),
            )
            statistics = backtest.run()
        native_trades = statistics["_trades"].copy(deep=True)
        native_equity = statistics["_equity_curve"].copy(deep=True)
        return native_trades, native_equity
