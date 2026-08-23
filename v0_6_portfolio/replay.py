"""Small, deterministic, long-only portfolio replay for V0.6."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date
from statistics import fmean, stdev

from v0_6_portfolio.contract import (
    AllocationMethod,
    PortfolioBar,
    PortfolioDecision,
    PortfolioFill,
    PortfolioPoint,
    PortfolioResult,
)


def _validate_bars(
    bars_by_symbol: Mapping[str, Sequence[PortfolioBar]],
) -> tuple[tuple[str, ...], tuple[date, ...]]:
    if not bars_by_symbol:
        raise ValueError("portfolio replay requires at least one symbol")
    symbols = tuple(sorted(bars_by_symbol))
    session_sets: list[tuple[date, ...]] = []
    for symbol in symbols:
        rows = tuple(bars_by_symbol[symbol])
        if not rows:
            raise ValueError(f"portfolio bars are empty for {symbol}")
        for bar in rows:
            bar.validate()
            if bar.symbol != symbol:
                raise ValueError(f"bar symbol mismatch for {symbol}")
        sessions = tuple(bar.session for bar in rows)
        if sessions != tuple(sorted(sessions)) or len(set(sessions)) != len(sessions):
            raise ValueError(
                f"portfolio sessions are not unique and chronological for {symbol}"
            )
        session_sets.append(sessions)
    if any(sessions != session_sets[0] for sessions in session_sets[1:]):
        raise ValueError("all portfolio symbols must share the same sessions")
    return symbols, session_sets[0]


def _volatility(
    bars: Sequence[PortfolioBar],
    *,
    end_index: int,
    lookback: int,
) -> float:
    if end_index < 0:
        return 1.0
    start = max(0, end_index - lookback + 1)
    closes = [bar.close for bar in bars[start : end_index + 1]]
    returns = [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes))]
    if len(returns) < 2:
        return 1.0
    value = stdev(returns)
    return value if math.isfinite(value) and value > 0 else 1.0


def build_trend_decisions(
    bars_by_symbol: Mapping[str, Sequence[PortfolioBar]],
    *,
    sma_window: int = 200,
    rebalance_every: int = 21,
) -> tuple[PortfolioDecision, ...]:
    """Build fixed-schedule target universes from confirmed closes only."""

    symbols, sessions = _validate_bars(bars_by_symbol)
    if sma_window < 2 or rebalance_every < 1:
        raise ValueError("sma_window must be >= 2 and rebalance_every must be positive")
    decisions: list[PortfolioDecision] = []
    first_decision_index = sma_window - 1
    for index in range(first_decision_index, len(sessions) - 1, rebalance_every):
        targets: list[str] = []
        for symbol in symbols:
            rows = bars_by_symbol[symbol]
            sma = fmean(bar.close for bar in rows[index + 1 - sma_window : index + 1])
            if rows[index].close > sma:
                targets.append(symbol)
        decisions.append(
            PortfolioDecision(
                decision_session=sessions[index],
                execution_session=sessions[index + 1],
                target_symbols=tuple(targets),
            )
        )
    return tuple(decisions)


def _weights(
    targets: tuple[str, ...],
    bars_by_symbol: Mapping[str, Sequence[PortfolioBar]],
    *,
    execution_index: int,
    allocation_method: AllocationMethod,
    volatility_lookback: int,
) -> dict[str, float]:
    if not targets:
        return {}
    if allocation_method == "equal_weight":
        weight = 1.0 / len(targets)
        return {symbol: weight for symbol in targets}
    if allocation_method == "inverse_vol":
        inverse = {
            symbol: 1.0
            / _volatility(
                bars_by_symbol[symbol],
                end_index=execution_index - 1,
                lookback=volatility_lookback,
            )
            for symbol in targets
        }
        total = sum(inverse.values())
        return {symbol: value / total for symbol, value in inverse.items()}
    raise ValueError(f"unsupported allocation method: {allocation_method}")


def replay_portfolio(
    bars_by_symbol: Mapping[str, Sequence[PortfolioBar]],
    decisions: Sequence[PortfolioDecision],
    *,
    allocation_method: AllocationMethod = "equal_weight",
    initial_cash: float = 100_000.0,
    friction_bps: float = 5.0,
    volatility_lookback: int = 20,
    evaluation_start: date | None = None,
    evaluation_end: date | None = None,
) -> PortfolioResult:
    """Replay shared cash, integer shares, and next-open rebalances.

    This is a reference portfolio contract, not an optimizer.  The allocation
    methods are predeclared baselines and all terminal positions remain marked
    to the last close without a synthetic liquidation.
    """

    symbols, sessions = _validate_bars(bars_by_symbol)
    if not math.isfinite(initial_cash) or initial_cash <= 0:
        raise ValueError("initial_cash must be finite and positive")
    if not math.isfinite(friction_bps) or friction_bps < 0:
        raise ValueError("friction_bps must be finite and non-negative")
    if volatility_lookback < 2:
        raise ValueError("volatility_lookback must be at least two")
    if (
        evaluation_start is not None
        and evaluation_end is not None
        and evaluation_end < evaluation_start
    ):
        raise ValueError("evaluation_end must not precede evaluation_start")
    start_index = 0
    end_index = len(sessions) - 1
    if evaluation_start is not None:
        if evaluation_start not in sessions:
            raise ValueError("evaluation_start is not an available portfolio session")
        start_index = sessions.index(evaluation_start)
    if evaluation_end is not None:
        if evaluation_end not in sessions:
            raise ValueError("evaluation_end is not an available portfolio session")
        end_index = sessions.index(evaluation_end)
    if start_index > end_index:
        raise ValueError("evaluation window has no portfolio sessions")
    for decision in decisions:
        decision.validate()
        if not set(decision.target_symbols).issubset(symbols):
            raise ValueError("portfolio decision contains an unknown symbol")
    decision_by_execution = {
        decision.execution_session: decision for decision in decisions
    }
    if len(decision_by_execution) != len(decisions):
        raise ValueError("portfolio decisions must have unique execution sessions")

    rows_by_symbol = {symbol: tuple(bars_by_symbol[symbol]) for symbol in symbols}
    cash = initial_cash
    positions = {symbol: 0 for symbol in symbols}
    fills: list[PortfolioFill] = []
    equity: list[PortfolioPoint] = []
    rate = friction_bps / 10_000
    applied_decisions = 0

    for index in range(start_index, end_index + 1):
        session = sessions[index]
        scheduled_decision = decision_by_execution.get(session)
        if scheduled_decision is not None:
            applied_decisions += 1
            weights = _weights(
                scheduled_decision.target_symbols,
                rows_by_symbol,
                execution_index=index,
                allocation_method=allocation_method,
                volatility_lookback=volatility_lookback,
            )
            open_prices = {
                symbol: rows_by_symbol[symbol][index].open for symbol in symbols
            }
            equity_at_open = cash + sum(
                positions[symbol] * open_prices[symbol] for symbol in symbols
            )
            target_quantities = {
                symbol: math.floor(
                    equity_at_open
                    * weights.get(symbol, 0.0)
                    / (open_prices[symbol] * (1 + rate))
                )
                for symbol in symbols
            }
            for symbol in symbols:
                quantity = positions[symbol] - target_quantities[symbol]
                if quantity <= 0:
                    continue
                price = open_prices[symbol]
                cost = quantity * price * rate
                cash += quantity * price - cost
                positions[symbol] -= quantity
                fills.append(
                    PortfolioFill(session, symbol, "sell", quantity, price, cost)
                )
            for symbol in symbols:
                quantity = target_quantities[symbol] - positions[symbol]
                if quantity <= 0:
                    continue
                price = open_prices[symbol]
                affordable = math.floor(cash / (price * (1 + rate)))
                quantity = min(quantity, affordable)
                if quantity == 0:
                    continue
                cost = quantity * price * rate
                cash -= quantity * price + cost
                positions[symbol] += quantity
                fills.append(
                    PortfolioFill(session, symbol, "buy", quantity, price, cost)
                )

        close_prices = {
            symbol: rows_by_symbol[symbol][index].close for symbol in symbols
        }
        gross = cash + sum(
            positions[symbol] * close_prices[symbol] for symbol in symbols
        )
        costs = sum(fill.modeled_cost for fill in fills)
        invested = tuple(symbol for symbol in symbols if positions[symbol] > 0)
        position_snapshot = tuple(
            (symbol, positions[symbol]) for symbol in symbols if positions[symbol] > 0
        )
        equity.append(
            PortfolioPoint(
                session=session,
                cash=cash,
                gross_equity=gross + costs,
                net_equity=gross,
                invested_symbols=invested,
                positions=position_snapshot,
            )
        )

    net = [point.net_equity for point in equity]
    returns = [net[0] / initial_cash - 1]
    returns.extend(net[index] / net[index - 1] - 1 for index in range(1, len(net)))
    running_max = net[0]
    drawdowns: list[float] = []
    for value in net:
        running_max = max(running_max, value)
        drawdowns.append(value / running_max - 1)
    total_return = net[-1] / initial_cash - 1
    observations = len(net)
    cagr = (net[-1] / initial_cash) ** (252 / observations) - 1
    sample_volatility = stdev(returns) if len(returns) > 1 else None
    volatility = (
        sample_volatility * math.sqrt(252) if sample_volatility is not None else None
    )
    sharpe = (
        fmean(returns) / sample_volatility * math.sqrt(252)
        if sample_volatility is not None and sample_volatility > 0
        else None
    )
    modeled_costs = sum(fill.modeled_cost for fill in fills)
    gross_return = equity[-1].gross_equity / initial_cash - 1
    turnover = (
        sum(fill.quantity * fill.price for fill in fills) / fmean(net) if net else None
    )
    return PortfolioResult(
        strategy_id="PORTFOLIO_TREND_SMA200_V1",
        allocation_method=allocation_method,
        initial_cash=initial_cash,
        fills=tuple(fills),
        equity=tuple(equity),
        metrics={
            "total_return": total_return,
            "CAGR": cagr,
            "annualized_volatility": volatility,
            "Sharpe": sharpe,
            "max_drawdown": min(drawdowns),
            "exposure": fmean(bool(point.invested_symbols) for point in equity),
            "turnover": turnover,
            "number_of_trades": sum(fill.side == "buy" for fill in fills),
            "number_of_fills": len(fills),
            "number_of_rebalances": applied_decisions,
            "observations": observations,
            "modeled_costs": modeled_costs,
            "gross_to_net_cost_drag": gross_return - total_return,
            "final_equity": net[-1],
        },
        decisions=tuple(decisions),
    )
