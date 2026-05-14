from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from brvm_package.data import get_asset_info, get_fundamental_history, get_market_dataframe


def _to_native(value: Any) -> Any:
    """Convertit np.float64/np.int64 en types Python natifs pour un affichage propre."""
    if isinstance(value, (np.floating, np.integer)):
        return float(value) if isinstance(value, np.floating) else int(value)
    if isinstance(value, dict):
        return {k: _to_native(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_native(v) for v in value]
    return value


def _fmt_pct(value: Any, decimals: int = 2) -> Any:
    """Formate un ratio en pourcentage lisible (ex: 0.06105 -> '6.11%')."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    try:
        return f"{float(value) * 100:.{decimals}f}%"
    except (TypeError, ValueError):
        return value


def _fmt_number(value: Any) -> Any:
    """Formate un grand nombre avec séparateurs de milliers."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    try:
        v = float(value)
        if v == int(v):
            return f"{int(v):,}"
        return f"{v:,.2f}"
    except (TypeError, ValueError):
        return value


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
        "market_cap_fmt": _fmt_number(info.get("market_cap")),
        "currency": info.get("currency", "XOF"),
        "shares_outstanding": info.get("shares_outstanding"),
        "shares_outstanding_fmt": _fmt_number(info.get("shares_outstanding")),
        "float_ratio": info.get("float_ratio"),
        "float_ratio_fmt": f"{info.get('float_ratio')}%" if info.get("float_ratio") is not None else None,
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
    result = result.sort_values("market_cap", ascending=False, na_position="last").reset_index(drop=True)

    # Formatage pour un affichage plus lisible
    result["market_cap_fmt"] = result["market_cap"].apply(_fmt_number)
    result["shares_outstanding_fmt"] = result["shares_outstanding"].apply(_fmt_number)
    result["weight_fmt"] = result["weight"].apply(lambda x: _fmt_pct(x, decimals=2))

    return result


def dividends(symbol: str) -> pd.DataFrame:
    info = get_asset_info(symbol)
    history = get_fundamental_history(symbol)
    if history.empty:
        return pd.DataFrame(columns=["Date", "Dividend", "Yield"])
    frame = history[["dividend"]].copy()
    frame.rename(columns={"dividend": "Dividend"}, inplace=True)
    frame["Yield"] = frame["Dividend"] / (info.get("last_price") or pd.NA)
    frame["Yield (%)"] = frame["Yield"].apply(lambda x: _fmt_pct(x))
    frame["Dividend_fmt"] = frame["Dividend"].apply(_fmt_number)
    frame.index.name = "Date"
    return frame


def fundamental_history(symbol: str, years: list[int] | None = None) -> pd.DataFrame:
    history = get_fundamental_history(symbol)
    if history.empty:
        return history
    if years is not None:
        history = history[history['fiscal_year'].isin(years)]


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


def financials(symbol: str, years: list[int] | None = None) -> dict[str, pd.DataFrame]:
    history = fundamental_history(symbol, years)
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
    income_statement["NetMargin (%)"] = income_statement["NetMargin"].apply(lambda x: _fmt_pct(x))
    income_statement["Revenue_fmt"] = income_statement["Revenue"].apply(_fmt_number)
    income_statement["NetIncome_fmt"] = income_statement["NetIncome"].apply(_fmt_number)

    balance_sheet = history[["shares_outstanding", "market_cap"]].rename(
        columns={"shares_outstanding": "SharesOutstanding", "market_cap": "MarketCap"}
    )
    balance_sheet["MarketCap_fmt"] = balance_sheet["MarketCap"].apply(_fmt_number)
    balance_sheet["SharesOutstanding_fmt"] = balance_sheet["SharesOutstanding"].apply(_fmt_number)

    cashflow = history[["dividend", "net_income", "payout_ratio"]].rename(
        columns={
            "dividend": "DividendCashProxy",
            "net_income": "NetIncomeProxy",
            "payout_ratio": "PayoutRatio",
        }
    )
    cashflow["PayoutRatio (%)"] = cashflow["PayoutRatio"].apply(lambda x: _fmt_pct(x))
    cashflow["DividendCashProxy_fmt"] = cashflow["DividendCashProxy"].apply(_fmt_number)
    cashflow["NetIncomeProxy_fmt"] = cashflow["NetIncomeProxy"].apply(_fmt_number)

    return {
        "income_statement": income_statement,
        "balance_sheet": balance_sheet,
        "cashflow": cashflow,
        "fundamental_history": history,
    }


def valuation_ratios(symbol: str, date: str | None = None) -> dict[str, Any]:
    """Ratios à date précise ou latest."""

    info = get_asset_info(symbol)
    history = fundamental_history(symbol)
    if date:
        snapshot = history[history.index == pd.to_datetime(date)].iloc[0] if not history[history.index == pd.to_datetime(date)].empty else {}
    else:
        snapshot = history.iloc[-1].to_dict() if not history.empty else {}
    per = snapshot.get('per') or info.get('per')
    earnings_yield = 1 / float(per) if per and per != 0 else None

    raw = {
        'symbol': info.get('symbol', symbol.upper()),
        'PER': per,
        'ROE': snapshot.get('roe') or info.get('roe'),
        'DividendYield': snapshot.get('dividend_yield') or info.get('dividend_yield'),
        'PriceToBook': snapshot.get('pbr') or info.get('pbr'),
        'EPS': snapshot.get('eps') or info.get('eps'),
        'EarningsYield': earnings_yield,
        'MarketCap': snapshot.get('market_cap') or info.get('market_cap'),
        'NetMargin': snapshot.get('net_margin') or info.get('net_margin'),
        'PayoutRatio': snapshot.get('payout_ratio') or info.get('payout_ratio'),
        'SharesOutstanding': snapshot.get('shares_outstanding') or info.get('shares_outstanding'),
        'FloatRatio': info.get('float_ratio'),
        'Beta1Y': info.get('beta_1y'),
        'date': date or 'latest',
    }

    # Formattage lisible
    formatted = _to_native(raw)
    formatted['DividendYield (%)'] = _fmt_pct(raw.get('DividendYield'))
    formatted['NetMargin (%)'] = _fmt_pct(raw.get('NetMargin'))
    formatted['PayoutRatio (%)'] = _fmt_pct(raw.get('PayoutRatio'))
    formatted['EarningsYield (%)'] = _fmt_pct(raw.get('EarningsYield'))
    formatted['FloatRatio (%)'] = f"{raw.get('FloatRatio')}%" if raw.get('FloatRatio') is not None else None
    formatted['ROE (%)'] = _fmt_pct(raw.get('ROE'))
    formatted['MarketCap_fmt'] = _fmt_number(raw.get('MarketCap'))
    formatted['SharesOutstanding_fmt'] = _fmt_number(raw.get('SharesOutstanding'))
    formatted['EPS_fmt'] = _fmt_number(raw.get('EPS'))

    return formatted


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.astype("float64") / denominator.replace({0: pd.NA}).astype("float64")
