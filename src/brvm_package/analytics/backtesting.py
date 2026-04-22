from __future__ import annotations

import inspect
from typing import Callable

import pandas as pd

from brvm_package.api.market import list_assets
from brvm_package.data import get_history_matrix
from brvm_package.fundamentals import market_cap_all

WeightsProvider = Callable[..., dict[str, float]]


def equal_weight_strategy(symbols: list[str] | None = None) -> WeightsProvider:
    universe = symbols or list_assets()

    def _strategy(_: pd.DataFrame) -> dict[str, float]:
        if not universe:
            return {}
        weight = 1 / len(universe)
        return {symbol: weight for symbol in universe}

    return _strategy


def market_cap_strategy(symbols: list[str] | None = None) -> WeightsProvider:
    def _strategy(_: pd.DataFrame) -> dict[str, float]:
        frame = market_cap_all()
        if symbols is not None:
            frame = frame[frame["symbol"].isin(symbols)]
        if frame.empty:
            return {}
        weights = frame.set_index("symbol")["weight"].fillna(0.0)
        total = weights.sum()
        if total == 0:
            return {}
        weights = weights / total
        return weights.to_dict()

    return _strategy


def momentum_strategy(lookback: int = 60, top_n: int = 3, symbols: list[str] | None = None) -> WeightsProvider:
    def _strategy(history: pd.DataFrame) -> dict[str, float]:
        price_matrix = history if not history.empty else get_history_matrix(symbols=symbols)
        if price_matrix.empty:
            return {}
        trailing = price_matrix.tail(lookback)
        scores = trailing.iloc[-1] / trailing.iloc[0] - 1
        winners = scores.nlargest(min(top_n, len(scores))).index.tolist()
        if not winners:
            return {}
        weight = 1 / len(winners)
        return {symbol: weight for symbol in winners}

    return _strategy


def value_strategy(
    max_pe: float = 15.0,
    min_dividend_yield: float = 0.02,
    top_n: int = 3,
    symbols: list[str] | None = None,
) -> WeightsProvider:
    from brvm_package.api.market import asset_info

    universe = symbols or list_assets()

    def _strategy(_: pd.DataFrame) -> dict[str, float]:
        picks: list[tuple[str, float]] = []
        for symbol in universe:
            info = asset_info(symbol)
            per = info.get("per")
            dy = info.get("dividend_yield") or 0.0
            if per is None or per > max_pe or dy < min_dividend_yield:
                continue
            picks.append((symbol, float(dy)))
        picks.sort(key=lambda item: item[1], reverse=True)
        selected = [symbol for symbol, _ in picks[:top_n]]
        if not selected:
            return {}
        weight = 1 / len(selected)
        return {symbol: weight for symbol in selected}

    return _strategy


def backtest(
    strategy: WeightsProvider,
    start: str | None = None,
    end: str | None = None,
    initial_cash: float = 1_000_000.0,
    symbols: list[str] | None = None,
    rebalance: str = "ME",
    transaction_cost: float = 0.001,
    slippage_bps: float = 5.0,
    cash_rate: float = 0.0,
) -> dict[str, object]:
    prices = get_history_matrix(symbols=symbols, start=start, end=end).ffill().dropna(how="all")
    if prices.empty:
        return {"equity_curve": pd.Series(dtype="float64"), "returns": pd.Series(dtype="float64"), "weights": {}, "summary": {}}

    rebal_dates = prices.resample(rebalance).last().index
    returns = prices.pct_change().fillna(0.0)
    current_weights = pd.Series(0.0, index=prices.columns, dtype="float64")
    portfolio_returns = pd.Series(0.0, index=prices.index, dtype="float64")
    weight_history: list[dict[str, object]] = []
    transaction_history: list[dict[str, object]] = []

    daily_cash_return = cash_rate / 252
    first_rebalance_done = False
    for current_date in prices.index:
        if current_date in rebal_dates or not first_rebalance_done:
            history_slice = prices.loc[:current_date]
            target_weights = _call_strategy(strategy, history_slice, current_date)
            if not target_weights:
                target_weights = equal_weight_strategy(symbols=list(prices.columns))(history_slice)

            target_series = pd.Series(target_weights, dtype="float64").reindex(prices.columns).fillna(0.0)
            target_total = target_series.sum()
            if target_total > 0:
                target_series = target_series / target_total

            turnover = float((target_series - current_weights).abs().sum())
            total_cost = turnover * (transaction_cost + slippage_bps / 10_000)
            transaction_history.append(
                {
                    "date": current_date,
                    "turnover": turnover,
                    "transaction_cost": turnover * transaction_cost,
                    "slippage_cost": turnover * (slippage_bps / 10_000),
                    "total_cost": total_cost,
                }
            )
            current_weights = target_series
            weight_history.append({"date": current_date, **current_weights.to_dict()})
            portfolio_returns.loc[current_date] -= total_cost
            first_rebalance_done = True

        invested_weight = float(current_weights.sum())
        asset_return = float((returns.loc[current_date] * current_weights).sum())
        cash_return_component = (1 - invested_weight) * daily_cash_return
        portfolio_returns.loc[current_date] += asset_return + cash_return_component

    equity_curve = initial_cash * (1 + portfolio_returns).cumprod()
    turnover_total = float(sum(item["turnover"] for item in transaction_history))
    total_cost_paid = float(sum(item["total_cost"] for item in transaction_history))
    volatility = float(portfolio_returns.std() * (252 ** 0.5))
    annualized_return = float(portfolio_returns.mean() * 252)
    sharpe = annualized_return / volatility if volatility else 0.0

    summary = {
        "initial_cash": initial_cash,
        "final_value": float(equity_curve.iloc[-1]),
        "total_return": float(equity_curve.iloc[-1] / initial_cash - 1),
        "annualized_return": annualized_return,
        "volatility": volatility,
        "sharpe": sharpe,
        "rebalances": int(len(rebal_dates)),
        "turnover": turnover_total,
        "cost_paid": total_cost_paid,
    }

    return {
        "equity_curve": equity_curve,
        "returns": portfolio_returns,
        "weights": current_weights.to_dict(),
        "weights_history": pd.DataFrame(weight_history).set_index("date") if weight_history else pd.DataFrame(),
        "transactions": pd.DataFrame(transaction_history).set_index("date") if transaction_history else pd.DataFrame(),
        "summary": summary,
    }


def _call_strategy(strategy: WeightsProvider, history: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, float]:
    try:
        parameters = inspect.signature(strategy).parameters
        if len(parameters) >= 2:
            return strategy(history, current_date)
    except (TypeError, ValueError):
        pass
    return strategy(history)
