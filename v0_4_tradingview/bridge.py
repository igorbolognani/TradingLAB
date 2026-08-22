"""Parse and validate TradingView observer payloads locally."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

OBSERVER_CONTRACT = "tradinglab/v0.4-observer/v1"
_FORBIDDEN_KEYS = {
    "api_key",
    "broker",
    "endpoint",
    "live",
    "order",
    "paper_account",
    "qty",
    "quantity",
    "secret",
}


def _string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class TradingViewSignal:
    """A confirmed observation emitted by the Pine indicator."""

    symbol: str
    timeframe: str
    session: date
    strategy_id: str
    strategy_version: str
    action: str
    indicator_value: float
    confirmed: bool
    source_revision: str
    contract: str = OBSERVER_CONTRACT
    schema_version: int = 1

    def to_payload(self) -> dict[str, object]:
        return {
            "contract": self.contract,
            "schema_version": self.schema_version,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "session": self.session.isoformat(),
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "action": self.action,
            "indicator_value": self.indicator_value,
            "confirmed": self.confirmed,
            "source_revision": self.source_revision,
        }


def parse_alert_payload(payload: str | Mapping[str, object]) -> TradingViewSignal:
    """Parse an alert payload while rejecting any execution-shaped fields."""

    if isinstance(payload, str):
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ValueError("TradingView payload is not valid JSON") from error
        if not isinstance(decoded, dict):
            raise ValueError("TradingView payload must be a JSON object")
        data: Mapping[str, object] = decoded
    else:
        data = payload
    forbidden = sorted(key for key in data if key.lower() in _FORBIDDEN_KEYS)
    if forbidden:
        raise ValueError(f"observer payload contains forbidden fields: {forbidden}")
    if _string(data, "contract") != OBSERVER_CONTRACT:
        raise ValueError("unsupported TradingView observer contract")
    schema_version = data.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != 1:
        raise ValueError("unsupported TradingView observer schema")
    confirmed = data.get("confirmed")
    if confirmed is not True:
        raise ValueError("only confirmed bars may enter the observer bridge")
    action = _string(data, "action")
    if action not in {"enter", "exit"}:
        raise ValueError("observer action must be enter or exit")
    indicator_value = data.get("indicator_value")
    if isinstance(indicator_value, bool) or not isinstance(
        indicator_value, (int, float)
    ):
        raise ValueError("indicator_value must be numeric")
    if not math.isfinite(float(indicator_value)):
        raise ValueError("indicator_value must be finite")
    session_raw = _string(data, "session")
    try:
        session = date.fromisoformat(session_raw)
    except ValueError as error:
        raise ValueError("session must be an ISO calendar date") from error
    return TradingViewSignal(
        symbol=_string(data, "symbol"),
        timeframe=_string(data, "timeframe"),
        session=session,
        strategy_id=_string(data, "strategy_id"),
        strategy_version=_string(data, "strategy_version"),
        action=action,
        indicator_value=float(indicator_value),
        confirmed=True,
        source_revision=_string(data, "source_revision"),
    )
