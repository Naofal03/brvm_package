from __future__ import annotations

from typing import Any

import pandas as pd

from brvm_package.analytics.returns import returns, returns_matrix


def volatility(symbol: str, annualization: int = 252) -> float | None:
    series = returns(symbol)
    if series.empty:
        return None
    return float(series.std() * (annualization ** 0.5))


def drawdown_series(symbol: str) -> pd.Series:
    series = returns(symbol)
    if series.empty:
        return pd.Series(dtype="float64")
    wealth = (1 + series).cumprod()
    peaks = wealth.cummax()
    return wealth / peaks - 1


def max_drawdown(symbol: str) -> float | None:
    series = drawdown_series(symbol)
    if series.empty:
        return None
    return float(series.min())


def beta(symbol: str, market_symbol: str | None = None) -> float | None:
    asset = returns(symbol)
    if asset.empty:
        return None
    benchmark = returns(market_symbol) if market_symbol else _market_proxy(asset.index)
    combined = pd.concat([asset, benchmark], axis=1, join="inner").dropna()
    if combined.empty or combined.iloc[:, 1].var() == 0:
        return None
    return float(combined.iloc[:, 0].cov(combined.iloc[:, 1]) / combined.iloc[:, 1].var())


def capm(symbol: str, market_symbol: str | None = None, risk_free_rate: float = 0.02) -> dict[str, Any]:
    b = beta(symbol, market_symbol=market_symbol)
    if b is None:
        return {"symbol": symbol.upper(), "expected_return": None, "alpha": None, "beta": None}
    asset = returns(symbol)
    benchmark = returns(market_symbol) if market_symbol else _market_proxy(asset.index)
    market_premium = benchmark.mean() * 252 - risk_free_rate
    expected_return = risk_free_rate + b * market_premium
    alpha = asset.mean() * 252 - expected_return
    return {"symbol": symbol.upper(), "expected_return": float(expected_return), "alpha": float(alpha), "beta": float(b)}


def var_historic(symbol: str, level: float = 0.05) -> float | None:
    series = returns(symbol)
    if series.empty:
        return None
    return float(series.quantile(level))


def cvar_historic(symbol: str, level: float = 0.05) -> float | None:
    series = returns(symbol)
    if series.empty:
        return None
    threshold = series.quantile(level)
    tail = series[series <= threshold]
    if tail.empty:
        return None
    return float(tail.mean())


def _market_proxy(index: pd.Index) -> pd.Series:
    matrix = returns_matrix()
    if matrix.empty:
        return pd.Series(dtype="float64")
    proxy = matrix.mean(axis=1)
    proxy = proxy.reindex(index).dropna()
    proxy.name = "market_proxy"
    return proxy
