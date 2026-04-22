import pandas as pd
from typing import Union, List
from brvm_package.objects.ticker import Ticker
from brvm_package.api.market import list_assets

def download(
    tickers: Union[str, List[str]],
    start: str | None = None,
    end: str | None = None,
    period: str | None = None,
) -> pd.DataFrame:
    """
    Télécharge/récupère les données historiques comme yfinance.download().
    """
    if isinstance(tickers, str):
        tickers = [tickers]
        
    dfs = []
    for symbol in tickers:
        ticker = Ticker(symbol)
        df_hist = ticker.history(start=start, end=end, period=period)
        
        # Ajout multi-index pour avoir la structure type yfinance
        df_hist['Symbol'] = symbol
        dfs.append(df_hist)
        
    if not dfs:
        return pd.DataFrame()
        
    res = pd.concat(dfs)
    # Pivot pour obtenir [Tickers, Colonnes]
    res_pivot = res.pivot(columns='Symbol')
    if len(tickers) == 1:
        res_pivot.columns = res_pivot.columns.droplevel(1)
        
    return res_pivot


def download_all(start: str | None = None, end: str | None = None, period: str | None = None) -> pd.DataFrame:
    """Télécharge tout l'univers local disponible."""
    return download(list_assets(), start=start, end=end, period=period)


def live_price(symbol: str) -> float | None:
    """Retourne le dernier prix disponible pour un actif."""
    return Ticker(symbol).live_price()


def returns(symbol: str, log: bool = False) -> pd.Series:
    """Retourne les rendements journaliers d'un actif."""
    return Ticker(symbol).returns(log=log)
