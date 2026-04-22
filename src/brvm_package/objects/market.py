from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from brvm_package.api.market import (
    asset_info,
    list_assets,
    list_countries,
    list_indices,
    list_sectors,
    market_summary,
)
from brvm_package.api.screener import screen
from brvm_package.analytics.returns import returns_matrix


@dataclass
class Market:
    def assets(self) -> list[str]:
        return list_assets()

    def indices(self, detailed: bool = False):
        return list_indices(detailed=detailed)

    def sectors(self) -> list[str]:
        return list_sectors()

    def countries(self) -> list[str]:
        return list_countries()

    def summary(self) -> dict:
        return market_summary()

    def info(self, symbol: str) -> dict:
        return asset_info(symbol)

    def screen(self, **criteria) -> pd.DataFrame:
        return screen(**criteria)

    def returns_matrix(self, symbols: list[str] | None = None) -> pd.DataFrame:
        return returns_matrix(symbols=symbols)
