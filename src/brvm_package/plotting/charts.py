from __future__ import annotations

from typing import Any

import pandas as pd

from brvm_package.api.market import asset_info
from brvm_package.data import get_history_matrix
from brvm_package.objects.ticker import Ticker


def plot_ticker(symbol: str, period: str | None = None) -> Any:
    history = Ticker(symbol).history(period=period)
    return _line_chart(history["Close"] if not history.empty else pd.Series(dtype="float64"), title=f"{symbol.upper()} Close")


def candlestick(symbol: str, period: str | None = None) -> Any:
    history = Ticker(symbol).history(period=period)
    if history.empty:
        return {"type": "candlestick", "title": f"{symbol.upper()} OHLC", "data": []}
    payload = history.reset_index().to_dict(orient="records")
    try:
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(history.index, history["Close"], label="Close", color="#0f766e")
        ax.fill_between(history.index, history["Low"], history["High"], color="#99f6e4", alpha=0.4)
        ax.set_title(f"{symbol.upper()} OHLC")
        ax.legend()
        return fig, ax
    except Exception:
        return {"type": "candlestick", "title": f"{symbol.upper()} OHLC", "data": payload}


def heatmap(symbols: list[str] | None = None, period: str | None = "1mo") -> Any:
    prices = get_history_matrix(symbols=symbols).ffill().dropna(how="all")
    if prices.empty:
        return {"type": "heatmap", "data": []}
    returns = prices.pct_change().dropna()
    if period:
        cutoff = returns.index.max() - pd.Timedelta("30D") if period == "1mo" else returns.index.min()
        returns = returns[returns.index >= cutoff]
    corr = returns.corr()
    try:
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(6, 5))
        image = ax.imshow(corr.to_numpy(), cmap="RdYlGn", vmin=-1, vmax=1)
        ax.set_xticks(range(len(corr.columns)), corr.columns, rotation=45, ha="right")
        ax.set_yticks(range(len(corr.index)), corr.index)
        ax.set_title("Correlation Heatmap")
        fig.colorbar(image, ax=ax)
        return fig, ax
    except Exception:
        return {"type": "heatmap", "matrix": corr.to_dict()}


def sector_allocation(weights: dict[str, float]) -> Any:
    rows = {}
    for symbol, weight in weights.items():
        sector = asset_info(symbol).get("sector", "Unknown")
        rows[sector] = rows.get(sector, 0.0) + float(weight)
    series = pd.Series(rows).sort_values(ascending=False)
    return _bar_chart(series, title="Sector Allocation")


def plot_allocation(weights: dict[str, float], title: str = "Allocation") -> Any:
    return _bar_chart(pd.Series(weights).sort_values(ascending=False), title=title)


def plot_equity_curve(curve: pd.Series, title: str = "Equity Curve") -> Any:
    return _line_chart(curve, title=title)


def _line_chart(series: pd.Series, title: str) -> Any:
    if series.empty:
        return {"type": "line", "title": title, "data": []}
    try:
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(series.index, series.values, color="#1d4ed8", linewidth=2)
        ax.set_title(title)
        ax.grid(alpha=0.2)
        return fig, ax
    except Exception:
        return {"type": "line", "title": title, "data": list(zip(series.index.astype(str), series.tolist(), strict=False))}


def _bar_chart(series: pd.Series, title: str) -> Any:
    if series.empty:
        return {"type": "bar", "title": title, "data": []}
    try:
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(series.index.astype(str), series.values, color="#ea580c")
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=45)
        return fig, ax
    except Exception:
        return {"type": "bar", "title": title, "data": series.to_dict()}
