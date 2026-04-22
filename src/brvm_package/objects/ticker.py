import pandas as pd
from pandas.tseries.frequencies import to_offset

from brvm_package.data import get_asset_info, get_history_frame, get_latest_price_row
from brvm_package.fundamentals import dividends as get_dividends
from brvm_package.fundamentals import financials as get_financials
from brvm_package.fundamentals import fundamental_history as get_fundamental_history
from brvm_package.fundamentals import valuation_ratios

class Ticker:
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        
    def history(
        self,
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """
        Récupère l'historique complet des prix de l'action.
        Similaire à `yfinance.Ticker.history()`.
        """
        df = get_history_frame(self.symbol)
        if df.empty:
            return df

        if period:
            offset = self._parse_period(period)
            if offset is not None:
                cutoff = df.index.max() - offset
                df = df[df.index >= cutoff]

        if start:
            df = df[df.index >= pd.to_datetime(start)]
        if end:
            df = df[df.index <= pd.to_datetime(end)]

        return df
            
    @property
    def info(self) -> dict:
        """
        Retourne les métadonnées, le dernier prix et le snapshot fondamental.
        """
        return get_asset_info(self.symbol)

    def live_price(self) -> float | None:
        latest_row = get_latest_price_row(self.symbol)
        close_price = latest_row.get("close_price")
        if close_price is None:
            return None
        return float(close_price)
            
    def returns(self, log: bool = False) -> pd.Series:
        """
        Retourne les rendements journaliers de l'action.
        """
        hist = self.history()
        if hist.empty or 'Close' not in hist:
            return pd.Series(dtype='float64')
        
        returns = hist['Close'].pct_change()
        if log:
            returns = (1 + returns).map(lambda value: pd.NA if pd.isna(value) or value <= 0 else value)
            returns = returns.dropna().map(float).map(__import__("math").log)
        return returns.dropna()

    def volatility(self, annualization: int = 252) -> float | None:
        series = self.returns()
        if series.empty:
            return None
        return float(series.std() * (annualization ** 0.5))

    def dividends(self) -> pd.DataFrame:
        return get_dividends(self.symbol)

    def financials(self) -> dict[str, pd.DataFrame]:
        return get_financials(self.symbol)

    def fundamental_history(self) -> pd.DataFrame:
        return get_fundamental_history(self.symbol)

    def valuation(self, date: str | None = None) -> dict:
        return valuation_ratios(self.symbol, date)

    def plot(self, period: str | None = None):
        from brvm_package.plotting.charts import plot_ticker

        return plot_ticker(self.symbol, period=period)

    def _parse_period(self, period: str) -> pd.Timedelta | None:
        normalized = period.strip().lower()
        aliases = {
            "1mo": "30D",
            "3mo": "90D",
            "6mo": "180D",
            "1y": "365D",
            "2y": "730D",
            "5y": "1825D",
            "10y": "3650D",
            "ytd": None,
            "max": None,
        }
        if normalized == "ytd":
            latest = self.history()
            if latest.empty:
                return None
            start_of_year = latest.index.max().normalize().replace(month=1, day=1)
            return latest.index.max() - start_of_year
        if normalized == "max":
            return None
        mapped = aliases.get(normalized, normalized)
        try:
            return pd.Timedelta(mapped)
        except (TypeError, ValueError):
            try:
                return pd.Timedelta(to_offset(mapped).delta)
            except (AttributeError, TypeError, ValueError):
                return None
