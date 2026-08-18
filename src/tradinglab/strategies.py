"""Engine-independent target transitions for the four canonical strategies."""

from dataclasses import dataclass
from typing import Literal

import pandas as pd

Action = Literal["enter", "exit"]


@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str
    indicator_value: float | None


class DecisionMachine:
    """Pure close-time decision rules driven by explicit portfolio state."""

    def __init__(self, strategy_id: str, parameters: dict[str, float | int]) -> None:
        self.strategy_id = strategy_id
        self.parameters = parameters

    def after_close(
        self,
        *,
        close: float,
        indicator: float,
        in_position: bool,
        held_sessions: int,
    ) -> Decision | None:
        """Return only a required target transition; unchanged targets emit nothing."""

        if self.strategy_id in {"CASH_0_V1", "BUY_HOLD_V1"}:
            return None
        available = not pd.isna(indicator)
        indicator_value = float(indicator) if available else None
        if self.strategy_id == "TREND_SMA200_V1":
            if not available:
                return None
            target_long = close > indicator
            if target_long and not in_position:
                return Decision("enter", "close_above_sma", indicator_value)
            if not target_long and in_position:
                return Decision("exit", "close_at_or_below_sma", indicator_value)
            return None
        if self.strategy_id == "MEANREV_Z20_V1":
            if in_position:
                if available and indicator >= float(self.parameters["exit_z"]):
                    return Decision("exit", "zscore_exit", indicator_value)
                if held_sessions >= int(self.parameters["max_hold"]):
                    return Decision("exit", "max_hold_exit", indicator_value)
                return None
            if available and indicator <= float(self.parameters["entry_z"]):
                return Decision("enter", "zscore_entry", indicator_value)
            return None
        raise ValueError(f"unsupported strategy: {self.strategy_id}")


def primary_parameters(strategy_id: str) -> dict[str, float | int]:
    """Return the frozen primary runtime parameters."""

    if strategy_id == "TREND_SMA200_V1":
        return {"sma": 200}
    if strategy_id == "MEANREV_Z20_V1":
        return {"lookback": 20, "entry_z": -2.0, "exit_z": 0.0, "max_hold": 10}
    if strategy_id in {"CASH_0_V1", "BUY_HOLD_V1"}:
        return {}
    raise ValueError(f"unsupported strategy: {strategy_id}")
