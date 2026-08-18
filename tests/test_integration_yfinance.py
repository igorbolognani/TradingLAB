import os
from datetime import date

import pytest

from tradinglab.data_source import RetrievalRequest, YFinanceSource


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("TRADINGLAB_NETWORK_TESTS") != "1",
    reason="set TRADINGLAB_NETWORK_TESTS=1 for explicit network integration",
)
def test_explicit_yfinance_network_contract() -> None:
    request = RetrievalRequest(
        symbols=("SPY",),
        start=date(2025, 1, 2),
        end_exclusive=date(2025, 1, 11),
    )
    result = YFinanceSource().fetch("SPY", request)
    assert not result.frame.empty
    assert {"Open", "High", "Low", "Close", "Adj Close", "Volume"}.issubset(
        result.frame.columns
    )
    assert result.exact_query_arguments["auto_adjust"] is False
    assert result.exact_query_arguments["actions"] is True
    assert result.exact_query_arguments["prepost"] is False
    assert result.exact_query_arguments["repair"] is False
    assert result.exact_query_arguments["hide_exceptions"] is False
    assert result.exact_query_arguments["raise_errors"] is None
