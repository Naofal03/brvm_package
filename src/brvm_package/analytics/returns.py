from __future__ import annotations

import pandas as pd

from brvm_package.api.market import list_assets
from brvm_package.objects.ticker import Ticker


def returns(symbol: str, log: bool = False) -> pd.Series:
    return Ticker(symbol).returns(log=log)


def returns_matrix(symbols: list[str] | None = None, log: bool = False) -> pd.DataFrame:
    tickers = symbols or list_assets()
    series_map: dict[str, pd.Series] = {}
    for symbol in tickers:
        current = Ticker(symbol).returns(log=log)
        if not current.empty:
            series_map[symbol] = current
    return pd.DataFrame(series_map)


def correlation_matrix(symbols: list[str] | None = None) -> pd.DataFrame:
    return returns_matrix(symbols=symbols).corr()
