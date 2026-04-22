from __future__ import annotations

from collections import defaultdict

import pandas as pd

from brvm_package.api.market import asset_info
from brvm_package.analytics.returns import returns_matrix


def sector_exposure(weights: dict[str, float]) -> pd.Series:
    exposure: dict[str, float] = defaultdict(float)
    for symbol, weight in weights.items():
        exposure[str(asset_info(symbol).get("sector", "Unknown"))] += float(weight)
    return pd.Series(dict(exposure)).sort_values(ascending=False)


def country_exposure(weights: dict[str, float]) -> pd.Series:
    exposure: dict[str, float] = defaultdict(float)
    for symbol, weight in weights.items():
        exposure[str(asset_info(symbol).get("country", "Unknown"))] += float(weight)
    return pd.Series(dict(exposure)).sort_values(ascending=False)


def factor_model(symbols: list[str] | None = None) -> pd.DataFrame:
    matrix = returns_matrix(symbols=symbols)
    if matrix.empty:
        return pd.DataFrame(columns=["market", "size", "value", "momentum"])

    latest_prices = matrix.count().sort_values()
    result = pd.DataFrame(index=matrix.columns)
    result["market"] = matrix.corrwith(matrix.mean(axis=1))
    result["size"] = latest_prices.rank(pct=True)
    result["value"] = [
        (asset_info(symbol).get("dividend_yield") or 0.0) - (asset_info(symbol).get("per") or 0.0) / 100
        for symbol in matrix.columns
    ]
    result["momentum"] = (1 + matrix).prod() - 1
    return result
