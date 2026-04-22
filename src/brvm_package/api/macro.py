from __future__ import annotations

import pandas as pd

from brvm_package.data import get_fcfa_exchange_rates, get_inflation_series, get_macro_events


def fcfa_exchange_rates() -> pd.DataFrame:
    return get_fcfa_exchange_rates()


def macro_events() -> pd.DataFrame:
    return get_macro_events()


def inflation() -> pd.DataFrame:
    return get_inflation_series()
