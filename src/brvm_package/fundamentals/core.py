from __future__ import annotations

from typing import Any

import pandas as pd

from brvm_package.data import get_asset_info, get_fundamental_history, get_latest_snapshot, get_market_dataframe


def shares_outstanding(symbol: str) -> float | None:
    info = get_asset_info(symbol)
    value = info.get("shares_outstanding")
    if value is None:
        return None
    return float(value)


def market_cap(symbol: str) -> dict[str, Any]:
    info = get_asset_info(symbol)
    return {
        "symbol": info.get("symbol", symbol.upper()),
        "market_cap": info.get("market_cap"),
        "currency": info.get("currency", "XOF"),
        "shares_outstanding": info.get("shares_outstanding"),
        "float_ratio": info.get("float_ratio"),
        "major_shareholders": info.get("major_shareholders"),
        "last_price": info.get("last_price"),
    }


def market_cap_all() -> pd.DataFrame:
    frame = get_market_dataframe()
    if frame.empty:
        return frame
    result = frame[["symbol", "market_cap", "last_price", "shares_outstanding", "sector", "country"]].copy()
    total_market_cap = result["market_cap"].fillna(0).sum()
    result["weight"] = result["market_cap"] / total_market_cap if total_market_cap else 0.0
    return result.sort_values("market_cap", ascending=False, na_position="last").reset_index(drop=True)


def dividends(symbol: str) -> pd.DataFrame:
    info = get_asset_info(symbol)
    history = get_fundamental_history(symbol)
    if history.empty:
        return pd.DataFrame(columns=["Date", "Dividend", "Yield"])
    frame = history[["dividend"]].copy()
    frame.rename(columns={"dividend": "Dividend"}, inplace=True)
    frame["Yield"] = frame["Dividend"] / (info.get("last_price") or pd.NA)
    frame.index.name = "Date"
    return frame


def fundamental_history(symbol: str) -> pd.DataFrame:
    history = get_fundamental_history(symbol)
    if history.empty:
        return history

    info = get_asset_info(symbol)
    price = info.get("last_price")
    history = history.copy()
    derived_shares = _safe_divide(history["net_income"], history["eps"])
    history["shares_outstanding"] = history["shares_outstanding"].where(history["shares_outstanding"].notna(), derived_shares)
    if price is not None:
        derived_market_cap = history["shares_outstanding"] * price
        history["market_cap"] = history["market_cap"].where(history["market_cap"].notna(), derived_market_cap)
    else:
        history["market_cap"] = history["market_cap"].where(history["market_cap"].notna(), pd.NA)
    history["dividend_yield"] = history["dividend"] / price if price not in (None, 0) else pd.NA
    history["earnings_yield"] = history["per"].map(lambda value: (1 / value) if pd.notna(value) and value not in (0, None) else pd.NA)
    history["net_margin"] = history["net_income"] / history["revenue"]
    history["payout_ratio"] = history["dividend"] / history["eps"]
    return history


def financials(symbol: str) -> dict[str, pd.DataFrame]:
    history = fundamental_history(symbol)
    if history.empty:
        empty = pd.DataFrame()
        return {
            "income_statement": empty,
            "balance_sheet": empty,
            "cashflow": empty,
            "fundamental_history": empty,
        }

    income_statement = history[["revenue", "net_income", "eps", "dividend", "net_margin"]].rename(
        columns={
            "revenue": "Revenue",
            "net_income": "NetIncome",
            "eps": "EPS",
            "dividend": "Dividend",
            "net_margin": "NetMargin",
        }
    )

    balance_sheet = history[["shares_outstanding", "market_cap"]].rename(
        columns={"shares_outstanding": "SharesOutstanding", "market_cap": "MarketCap"}
    )

    cashflow = history[["dividend", "net_income", "payout_ratio"]].rename(
        columns={
            "dividend": "DividendCashProxy",
            "net_income": "NetIncomeProxy",
            "payout_ratio": "PayoutRatio",
        }
    )

    return {
        "income_statement": income_statement,
        "balance_sheet": balance_sheet,
        "cashflow": cashflow,
        "fundamental_history": history,
    }


def valuation_ratios(symbol: str, date: str | None = None) -> dict[str, Any]:
    """Ratios à date précise ou latest."""

    info = get_asset_info(symbol)
    history = get_fundamental_history(symbol)
    if date:
        snapshot = history[history.index == pd.to_datetime(date)].iloc[0] if not history[history.index == pd.to_datetime(date)].empty else {}
    else:
        snapshot = history.iloc[-1].to_dict() if not history.empty else {}
    price = info.get('last_price', info.get('close_price'))
    per = snapshot.get('per') or info.get('per')
    earnings_yield = 1 / float(per) if per and per != 0 else None

    return {
        'symbol': info.get('symbol', symbol.upper()),
        'PER': per,
        'ROE': snapshot.get('roe'),
        'DividendYield': snapshot.get('dividend_yield') or snapshot.get('dividend') / price if price else None,
        'PriceToBook': snapshot.get('pbr'),
        'EPS': snapshot.get('eps'),
        'EarningsYield': earnings_yield,
        'MarketCap': snapshot.get('market_cap'),
        'NetMargin': snapshot.get('net_margin'),
        'PayoutRatio': snapshot.get('payout_ratio'),
        'SharesOutstanding': snapshot.get('shares_outstanding'),
        'FloatRatio': info.get('float_ratio'),
        'Beta1Y': info.get('beta_1y'),
        'date': date or 'latest',
    }


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.astype("float64") / denominator.replace({0: pd.NA}).astype("float64")

