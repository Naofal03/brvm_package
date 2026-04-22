from __future__ import annotations

import pandas as pd

from brvm_package.data import get_market_dataframe, normalize_sector_name


def screen(
    query: str | None = None,
    sector: str | None = None,
    country: str | None = None,
    min_dividend_yield: float | None = None,
    max_dividend_yield: float | None = None,
    min_market_cap: float | None = None,
    max_market_cap: float | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    max_pe: float | None = None,
    min_pe: float | None = None,
    min_net_margin: float | None = None,
    min_payout_ratio: float | None = None,
    filters: dict[str, object] | None = None,
    sort_by: str | list[str] | None = None,
    ascending: bool | list[bool] = False,
    columns: list[str] | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    frame = get_market_dataframe()
    if frame.empty:
        return frame

    result = frame.copy()
    if query is not None:
        lowered = query.lower()
        mask = (
            result["symbol"].fillna("").str.lower().str.contains(lowered)
            | result["name"].fillna("").str.lower().str.contains(lowered)
            | result["sector"].fillna("").str.lower().str.contains(lowered)
            | result["country"].fillna("").str.lower().str.contains(lowered)
        )
        result = result[mask]
    if sector is not None:
        canonical_sector = normalize_sector_name(sector)
        result = result[result["sector"].fillna("").str.lower() == canonical_sector.lower()]
    if country is not None:
        result = result[result["country"].fillna("").str.lower() == country.lower()]
    if min_dividend_yield is not None:
        result = result[result["dividend_yield"].fillna(-1) >= min_dividend_yield]
    if max_dividend_yield is not None:
        result = result[result["dividend_yield"].fillna(float("inf")) <= max_dividend_yield]
    if min_market_cap is not None:
        result = result[result["market_cap"].fillna(-1) >= min_market_cap]
    if max_market_cap is not None:
        result = result[result["market_cap"].fillna(float("inf")) <= max_market_cap]
    if min_price is not None:
        result = result[result["last_price"].fillna(-1) >= min_price]
    if max_price is not None:
        result = result[result["last_price"].fillna(float("inf")) <= max_price]
    if max_pe is not None:
        result = result[result["per"].fillna(float("inf")) <= max_pe]
    if min_pe is not None:
        result = result[result["per"].fillna(-1) >= min_pe]
    if min_net_margin is not None:
        result = result[result["net_margin"].fillna(-1) >= min_net_margin]
    if min_payout_ratio is not None:
        result = result[result["payout_ratio"].fillna(-1) >= min_payout_ratio]
    if filters:
        result = _apply_filters(result, filters)

    sort_columns = sort_by or ["market_cap", "dividend_yield"]
    result = result.sort_values(sort_columns, ascending=ascending, na_position="last")
    if columns is not None:
        result = result[[column for column in columns if column in result.columns]]
    if limit is not None:
        result = result.head(limit)
    return result.reset_index(drop=True)


def _apply_filters(frame: pd.DataFrame, filters: dict[str, object]) -> pd.DataFrame:
    result = frame
    for field, rule in filters.items():
        if field not in result.columns:
            continue
        if isinstance(rule, tuple) and len(rule) == 2:
            operator, value = rule
            if operator == ">":
                result = result[result[field] > value]
            elif operator == ">=":
                result = result[result[field] >= value]
            elif operator == "<":
                result = result[result[field] < value]
            elif operator == "<=":
                result = result[result[field] <= value]
            elif operator == "==":
                result = result[result[field] == value]
            elif operator == "!=":
                result = result[result[field] != value]
            elif operator == "contains":
                result = result[result[field].fillna("").astype(str).str.contains(str(value), case=False)]
        else:
            result = result[result[field] == rule]
    return result
