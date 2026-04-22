from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from brvm_package.data.catalog import (
    get_asset_catalog,
    get_asset_metadata,
    get_country_names,
    get_sector_names,
    merge_asset_metadata,
)
from brvm_package.db.paths import ensure_database_path_ready

SNAPSHOT_COLUMNS = [
    "symbol",
    "snapshot_date",
    "revenue",
    "net_income",
    "eps",
    "per",
    "pbr",
    "roe",
    "dividend",
    "market_cap",
    "shares_outstanding",
    "float_ratio",
    "beta_1y",
    "major_shareholders",
    "source",
]

LEGACY_SNAPSHOT_COLUMNS = [
    "symbol",
    "snapshot_date",
    "revenue",
    "net_income",
    "eps",
    "per",
    "dividend",
    "source",
]


def get_db_connection() -> sqlite3.Connection:
    return sqlite3.connect(ensure_database_path_ready())


def get_available_symbols() -> list[str]:
    catalog_symbols = {symbol.upper() for symbol in get_asset_catalog()}
    query = """
    SELECT symbol FROM daily_prices
    UNION
    SELECT symbol FROM fundamental_snapshots
    ORDER BY symbol
    """
    try:
        with get_db_connection() as conn:
            df = pd.read_sql_query(query, conn)
    except Exception:
        return sorted(catalog_symbols)
    db_symbols = set(df["symbol"].astype(str).str.upper().tolist())
    return sorted(db_symbols | catalog_symbols)


def get_history_frame(symbol: str) -> pd.DataFrame:
    query = """
    SELECT
        date AS Date,
        open_price AS Open,
        high_price AS High,
        low_price AS Low,
        close_price AS Close,
        volume AS Volume
    FROM daily_prices
    WHERE symbol = ?
    ORDER BY date ASC
    """
    try:
        with get_db_connection() as conn:
            df = pd.read_sql_query(query, conn, params=(symbol.upper(),))
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return df

    df["Date"] = pd.to_datetime(df["Date"])
    df.set_index("Date", inplace=True)
    return df


def get_latest_snapshot(symbol: str) -> dict[str, Any]:
    query = """
    SELECT
        symbol,
        snapshot_date,
        revenue,
        net_income,
        eps,
        per,
        pbr,
        roe,
        dividend,
        market_cap,
        shares_outstanding,
        float_ratio,
        beta_1y,
        major_shareholders,
        source
    FROM fundamental_snapshots
    WHERE symbol = ?
    ORDER BY snapshot_date DESC
    LIMIT 1
    """
    df = _read_snapshot_query(query, symbol, latest=True)
    if df.empty:
        return {}
    return df.iloc[0].to_dict()


def get_fundamental_history(symbol: str) -> pd.DataFrame:
    query = """
    SELECT
        symbol,
        snapshot_date,
        revenue,
        net_income,
        eps,
        per,
        pbr,
        roe,
        dividend,
        market_cap,
        shares_outstanding,
        float_ratio,
        beta_1y,
        major_shareholders,
        source
    FROM fundamental_snapshots
    WHERE symbol = ?
    ORDER BY snapshot_date ASC
    """
    df = _read_snapshot_query(query, symbol, latest=False)
    if df.empty:
        return df
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
    df.set_index("snapshot_date", inplace=True)
    return df


def get_latest_price_row(symbol: str) -> dict[str, Any]:
    query = """
    SELECT
        symbol,
        date,
        open_price,
        high_price,
        low_price,
        close_price,
        volume,
        source
    FROM daily_prices
    WHERE symbol = ?
    ORDER BY date DESC
    LIMIT 1
    """
    try:
        with get_db_connection() as conn:
            df = pd.read_sql_query(query, conn, params=(symbol.upper(),))
    except Exception:
        return {}
    if df.empty:
        return {}
    return df.iloc[0].to_dict()


def get_asset_info(symbol: str) -> dict[str, Any]:
    normalized_symbol = symbol.upper()
    history = get_history_frame(normalized_symbol)
    latest_price = get_latest_price_row(normalized_symbol)
    latest_snapshot = get_latest_snapshot(normalized_symbol)
    metadata = get_asset_metadata(normalized_symbol)

    if history.empty and not latest_snapshot and not metadata:
        return {}

    info: dict[str, Any] = merge_asset_metadata(normalized_symbol)
    info.update(
        {
            "currency": "XOF",
            "history_rows": int(len(history)),
            "first_trade_date": history.index.min().date().isoformat() if not history.empty else None,
            "last_trade_date": history.index.max().date().isoformat() if not history.empty else None,
        }
    )

    if latest_price:
        info.update(
            {
                "last_price": latest_price.get("close_price"),
                "last_open": latest_price.get("open_price"),
                "last_high": latest_price.get("high_price"),
                "last_low": latest_price.get("low_price"),
                "last_volume": latest_price.get("volume"),
                "price_source": latest_price.get("source"),
            }
        )

    if latest_snapshot:
        info.update(latest_snapshot)
        shares_outstanding = latest_snapshot.get("shares_outstanding")
        if shares_outstanding is None:
            shares_outstanding = _safe_divide(latest_snapshot.get("net_income"), latest_snapshot.get("eps"))
        market_cap = latest_snapshot.get("market_cap")
        if shares_outstanding is not None and info.get("last_price") is not None:
            market_cap = market_cap or (shares_outstanding * float(info["last_price"]))
        info["shares_outstanding"] = shares_outstanding
        info["market_cap"] = market_cap
        info["dividend_yield"] = _safe_divide(latest_snapshot.get("dividend"), info.get("last_price"))
        info["earnings_yield"] = _safe_divide(1, latest_snapshot.get("per"))
        info["net_margin"] = _safe_divide(latest_snapshot.get("net_income"), latest_snapshot.get("revenue"))
        info["payout_ratio"] = _safe_divide(latest_snapshot.get("dividend"), latest_snapshot.get("eps"))
        info["pbr"] = latest_snapshot.get("pbr")
        info["roe"] = latest_snapshot.get("roe")
        info["float_ratio"] = latest_snapshot.get("float_ratio")
        info["beta_1y"] = latest_snapshot.get("beta_1y")
        info["major_shareholders"] = latest_snapshot.get("major_shareholders")

    return info


def search_assets(query: str) -> pd.DataFrame:
    needle = query.strip().lower()
    symbols = sorted(set(get_available_symbols()) | set(get_asset_catalog()))

    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        metadata = merge_asset_metadata(symbol)
        haystacks = [
            symbol.lower(),
            str(metadata.get("name", "")).lower(),
            str(metadata.get("sector", "")).lower(),
            str(metadata.get("country", "")).lower(),
        ]
        if not needle or any(needle in haystack for haystack in haystacks):
            rows.append(metadata)

    return pd.DataFrame(rows)


def get_market_summary() -> dict[str, Any]:
    query = """
    WITH latest AS (
        SELECT MAX(date) AS latest_date FROM daily_prices
    ),
    ranked AS (
        SELECT
            symbol,
            date,
            close_price,
            volume,
            LAG(close_price) OVER (PARTITION BY symbol ORDER BY date) AS previous_close
        FROM daily_prices
    )
    SELECT
        r.date AS market_date,
        COUNT(*) AS assets,
        SUM(CASE WHEN r.close_price > r.previous_close THEN 1 ELSE 0 END) AS advancers,
        SUM(CASE WHEN r.close_price < r.previous_close THEN 1 ELSE 0 END) AS decliners,
        SUM(CASE WHEN r.close_price = r.previous_close THEN 1 ELSE 0 END) AS unchanged,
        SUM(COALESCE(r.volume, 0)) AS total_volume,
        AVG(r.close_price) AS average_close
    FROM ranked r
    JOIN latest l ON r.date = l.latest_date
    """
    try:
        with get_db_connection() as conn:
            df = pd.read_sql_query(query, conn)
    except Exception:
        return {}
    if df.empty:
        return {}
    return df.iloc[0].to_dict()


def get_history_matrix(
    symbols: list[str] | None = None,
    field: str = "Close",
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    selected_symbols = symbols or get_available_symbols()
    series_map: dict[str, pd.Series] = {}

    for symbol in selected_symbols:
        history = get_history_frame(symbol)
        if history.empty or field not in history.columns:
            continue
        current = history[field].copy()
        if start:
            current = current[current.index >= pd.to_datetime(start)]
        if end:
            current = current[current.index <= pd.to_datetime(end)]
        if not current.empty:
            series_map[symbol.upper()] = current

    return pd.DataFrame(series_map).sort_index()


def get_market_dataframe() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for symbol in get_available_symbols():
        info = get_asset_info(symbol)
        if info:
            rows.append(info)
    return pd.DataFrame(rows)


def get_available_sectors() -> list[str]:
    return get_sector_names()


def get_available_countries() -> list[str]:
    return get_country_names()


def _safe_divide(numerator: Any, denominator: Any) -> float | None:
    try:
        if numerator is None or denominator in (None, 0):
            return None
        return float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _read_snapshot_query(query: str, symbol: str, latest: bool) -> pd.DataFrame:
    try:
        with get_db_connection() as conn:
            df = pd.read_sql_query(query, conn, params=(symbol.upper(),))
    except Exception:
        order_clause = "DESC LIMIT 1" if latest else "ASC"
        fallback_query = f"""
        SELECT
            symbol,
            snapshot_date,
            revenue,
            net_income,
            eps,
            per,
            dividend,
            source
        FROM fundamental_snapshots
        WHERE symbol = ?
        ORDER BY snapshot_date {order_clause}
        """
        try:
            with get_db_connection() as conn:
                df = pd.read_sql_query(fallback_query, conn, params=(symbol.upper(),))
        except Exception:
            return pd.DataFrame()
        for column in SNAPSHOT_COLUMNS:
            if column not in df.columns:
                df[column] = pd.NA
        df = df[SNAPSHOT_COLUMNS]
    return df
