import json

import pytest

from v0_4_tradingview.bridge import OBSERVER_CONTRACT, parse_alert_payload


def _payload() -> dict[str, object]:
    return {
        "contract": OBSERVER_CONTRACT,
        "schema_version": 1,
        "symbol": "SPY",
        "timeframe": "D",
        "session": "2026-08-21",
        "strategy_id": "TREND_SMA200_V1",
        "strategy_version": "V1",
        "action": "enter",
        "indicator_value": 500.25,
        "confirmed": True,
        "source_revision": "pine-v6-observer-1",
    }


def test_tradingview_payload_is_parsed_as_observation() -> None:
    signal = parse_alert_payload(json.dumps(_payload()))
    assert signal.symbol == "SPY"
    assert signal.session.isoformat() == "2026-08-21"
    assert signal.confirmed is True


def test_unconfirmed_bar_is_rejected() -> None:
    payload = _payload()
    payload["confirmed"] = False
    with pytest.raises(ValueError, match="confirmed"):
        parse_alert_payload(payload)


def test_execution_shaped_payload_is_rejected() -> None:
    payload = _payload()
    payload["quantity"] = 10
    with pytest.raises(ValueError, match="forbidden"):
        parse_alert_payload(payload)


def test_boolean_schema_version_is_rejected() -> None:
    payload = _payload()
    payload["schema_version"] = True
    with pytest.raises(ValueError, match="schema"):
        parse_alert_payload(payload)
