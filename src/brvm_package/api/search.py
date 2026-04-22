from __future__ import annotations

import pandas as pd

from brvm_package.data import search_assets


def search(query: str) -> pd.DataFrame:
    return search_assets(query)
