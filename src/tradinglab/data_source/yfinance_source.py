"""The sole V0.1 provider/network boundary, with no implicit data semantics."""

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from tradinglab.constants import ASSETS, REQUESTED_END_EXCLUSIVE, REQUESTED_START


def _load_yfinance() -> Any:
    """Load the private Yahoo connector only when that path is requested."""

    try:
        import yfinance as yf
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "the private Yahoo path is optional; install it with "
            "`uv sync --extra yahoo --all-groups`"
        ) from exc
    return yf


@dataclass(frozen=True)
class RetrievalRequest:
    """Explicit immutable request for one dataset refresh."""

    symbols: tuple[str, ...] = ASSETS
    start: date = REQUESTED_START
    end_exclusive: date = REQUESTED_END_EXCLUSIVE

    def __post_init__(self) -> None:
        if not self.symbols or any(symbol not in ASSETS for symbol in self.symbols):
            raise ValueError(
                "symbols must be a non-empty subset of the canonical assets"
            )
        if len(set(self.symbols)) != len(self.symbols):
            raise ValueError("symbols must be unique")
        if self.start >= self.end_exclusive:
            raise ValueError("start must precede end_exclusive")
        if self.end_exclusive > REQUESTED_END_EXCLUSIVE:
            raise ValueError("V0.1 must never request or accept a 2026 observation")


@dataclass(frozen=True)
class ProviderFrame:
    """Provider output and query provenance before any normalization."""

    symbol: str
    frame: pd.DataFrame
    provider: str
    provider_version: str
    exact_query_arguments: dict[str, Any]


class YFinanceSource:
    """Small replaceable yfinance connector for personal research only."""

    provider = "yfinance/Yahoo"

    @staticmethod
    def query_arguments(request: RetrievalRequest) -> dict[str, Any]:
        """Return every material `Ticker.history` semantic explicitly."""

        return {
            "period": None,
            "start": request.start.isoformat(),
            "end": request.end_exclusive.isoformat(),
            "interval": "1d",
            "prepost": False,
            "actions": True,
            "auto_adjust": False,
            "back_adjust": False,
            "repair": False,
            "keepna": True,
            "rounding": False,
            "timeout": 30,
            "raise_errors": None,
            "hide_exceptions": False,
            "group_by": None,
            "multi_level_index": None,
            "threads": None,
            "ignore_tz": None,
            "timezone_behavior": "Ticker.history preserves the exchange index timezone",
            "missing_row_behavior": (
                "keepna=True; no downstream forward fill or silent drop"
            ),
        }

    def fetch(self, symbol: str, request: RetrievalRequest) -> ProviderFrame:
        """Perform one explicit single-symbol network request."""

        if symbol not in request.symbols:
            raise ValueError(f"{symbol} is not declared in this retrieval request")
        yf = _load_yfinance()
        arguments = self.query_arguments(request)
        # yfinance 1.6.0 deprecated the per-call raise_errors argument in favor
        # of this explicit process configuration.
        yf.config.debug.hide_exceptions = False
        ticker = yf.Ticker(symbol)
        frame = ticker.history(
            period=None,
            start=arguments["start"],
            end=arguments["end"],
            interval="1d",
            prepost=False,
            actions=True,
            auto_adjust=False,
            back_adjust=False,
            repair=False,
            keepna=True,
            rounding=False,
            timeout=30,
        )
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            raise ValueError(f"provider returned no rows for {symbol}")
        return ProviderFrame(
            symbol=symbol,
            frame=frame.copy(deep=True),
            provider=self.provider,
            provider_version=yf.__version__,
            exact_query_arguments=arguments,
        )
