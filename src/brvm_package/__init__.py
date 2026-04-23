# Expose financial reports API
from brvm_package.financial_reports.api import get_financials, list_available_years
from importlib.metadata import PackageNotFoundError, version

from .objects.index import Index
from .objects.market import Market
from .objects.portfolio import Portfolio
from .objects.ticker import Ticker
from .api.download import download, download_all, live_price, returns
from .api.fundamentals import dividends, financials, fundamental_history, market_cap, market_cap_all, shares_outstanding, valuation_ratios
from .api.macro import fcfa_exchange_rates, inflation, macro_events
from .api.market import (
    asset_info,
    get_market,
    list_assets,
    list_stocks,
    list_countries,
    list_indices,
    list_sectors,
    market_summary,
    search,
)
from .api.screener import screen
from .api.strategies import backtest, equal_weight_strategy, market_cap_strategy, momentum_strategy, value_strategy
from .plotting.charts import candlestick, heatmap, sector_allocation

try:
    __version__ = version("brvm")
except PackageNotFoundError:
    __version__ = "0.2.0"

__all__ = [
    "Index",
    "Market",
    "Portfolio",
    "Ticker",
    "__version__",
    "asset_info",
    "backtest",
    "candlestick",
    "dividends",
    "download_all",
    "equal_weight_strategy",
    "fcfa_exchange_rates",
    "financials",
    "fundamental_history",
    "get_market",
    "heatmap",
    "inflation",
    "live_price",
    "list_countries",
    "macro_events",
    "market_cap",
    "market_cap_all",
    "market_cap_strategy",
    "market_summary",
    "momentum_strategy",
    "returns",
    "screen",
    "search",
    "sector_allocation",
    "shares_outstanding",
    "value_strategy",
    "valuation_ratios",
    "list_assets",
    "list_stocks",
    "list_indices",
    "list_sectors",
    "download",
]
