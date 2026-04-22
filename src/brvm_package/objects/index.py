from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from brvm_package.api.market import list_indices
from brvm_package.data import get_history_matrix


@dataclass
class Index:
    symbol: str

    @property
    def info(self) -> dict[str, str] | None:
        detailed = list_indices(detailed=True)
        if isinstance(detailed, pd.DataFrame):
            matches = detailed[detailed["symbol"] == self.symbol]
            if not matches.empty:
                return matches.iloc[0].to_dict()
        return None

    def history(self, start: str | None = None, end: str | None = None) -> pd.Series:
        prices = get_history_matrix(start=start, end=end)
        if prices.empty:
            return pd.Series(dtype="float64")
        synthetic = prices.ffill().pct_change().mean(axis=1).fillna(0.0)
        index_level = 100 * (1 + synthetic).cumprod()
        index_level.name = self.symbol
        return index_level
