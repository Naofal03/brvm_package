from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from brvm_package.analytics.backtesting import backtest
from brvm_package.analytics.factors import country_exposure, sector_exposure
from brvm_package.analytics.optimization import efficient_frontier, optimize_portfolio
from brvm_package.data import get_history_matrix


@dataclass
class Portfolio:
    symbols: list[str] | None = None
    weights: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.symbols and not self.weights:
            equal = 1 / len(self.symbols)
            self.weights = {symbol.upper(): equal for symbol in self.symbols}
        else:
            self.weights = {symbol.upper(): float(weight) for symbol, weight in self.weights.items()}
        self._normalize_weights()

    def add(self, symbol: str, weight: float | None = None) -> "Portfolio":
        self.weights[symbol.upper()] = float(weight) if weight is not None else 0.0
        self._normalize_weights()
        return self

    def set_weights(self, weights: dict[str, float]) -> "Portfolio":
        self.weights = {symbol.upper(): float(weight) for symbol, weight in weights.items()}
        self._normalize_weights()
        return self

    def history(self, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        return get_history_matrix(symbols=list(self.weights), start=start, end=end)

    def returns(self, start: str | None = None, end: str | None = None) -> pd.Series:
        prices = self.history(start=start, end=end).ffill().dropna(how="all")
        if prices.empty:
            return pd.Series(dtype="float64")
        normalized = pd.Series(self.weights).reindex(prices.columns).fillna(0.0)
        normalized = normalized / normalized.sum()
        return prices.pct_change().fillna(0.0).mul(normalized, axis=1).sum(axis=1)

    def optimize(self, method: str = "markowitz", risk_free_rate: float = 0.02) -> dict[str, float]:
        prices = self.history().ffill().dropna(how="all")
        result = optimize_portfolio(prices.pct_change().dropna(), method=method, risk_free_rate=risk_free_rate)
        self.weights = result.weights
        self._normalize_weights()
        return self.weights

    def efficient_frontier(self, points: int = 25) -> pd.DataFrame:
        prices = self.history().ffill().dropna(how="all")
        return efficient_frontier(prices.pct_change().dropna(), points=points)

    def performance(self) -> dict[str, float | None]:
        series = self.returns()
        if series.empty:
            return {"annual_return": None, "volatility": None, "sharpe": None, "sortino": None, "alpha": None}
        annual_return = float(series.mean() * 252)
        volatility = float(series.std() * (252 ** 0.5))
        downside = series[series < 0].std() * (252 ** 0.5)
        sortino = float(annual_return / downside) if downside else None
        sharpe = float(annual_return / volatility) if volatility else None
        return {"annual_return": annual_return, "volatility": volatility, "sharpe": sharpe, "sortino": sortino, "alpha": None}

    def sharpe(self) -> float | None:
        return self.performance()["sharpe"]

    def drawdown(self) -> pd.Series:
        series = self.returns()
        if series.empty:
            return pd.Series(dtype="float64")
        wealth = (1 + series).cumprod()
        return wealth / wealth.cummax() - 1

    def rebalance(self, weights: dict[str, float] | None = None) -> dict[str, float]:
        if weights is not None:
            self.weights = {symbol.upper(): float(weight) for symbol, weight in weights.items()}
        self._normalize_weights()
        return self.weights

    def backtest(
        self,
        initial_cash: float = 1_000_000.0,
        rebalance: str = "ME",
        transaction_cost: float = 0.001,
        slippage_bps: float = 5.0,
        cash_rate: float = 0.0,
    ) -> dict[str, object]:
        def strategy(_: pd.DataFrame) -> dict[str, float]:
            return self.weights

        return backtest(
            strategy=strategy,
            initial_cash=initial_cash,
            symbols=list(self.weights),
            rebalance=rebalance,
            transaction_cost=transaction_cost,
            slippage_bps=slippage_bps,
            cash_rate=cash_rate,
        )

    def sector_exposure(self) -> pd.Series:
        return sector_exposure(self.weights)

    def country_exposure(self) -> pd.Series:
        return country_exposure(self.weights)

    def plot(self):
        from brvm_package.plotting.charts import plot_equity_curve

        return plot_equity_curve(self.backtest()["equity_curve"], title="Portfolio Equity Curve")

    def plot_allocation(self):
        from brvm_package.plotting.charts import plot_allocation

        return plot_allocation(self.weights, title="Portfolio Allocation")

    def _normalize_weights(self) -> None:
        if not self.weights:
            return
        total = sum(weight for weight in self.weights.values() if weight >= 0)
        if total <= 0:
            equal = 1 / len(self.weights)
            self.weights = {symbol: equal for symbol in self.weights}
            return
        self.weights = {symbol: weight / total for symbol, weight in self.weights.items()}
