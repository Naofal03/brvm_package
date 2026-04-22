# brvm-package [![Tests: 17/17](https://img.shields.io/badge/tests-17--17-brightgreen) [![PyPI](https://badge.fury.io/py/brvm-package.svg)](https://pypi.org/project/brvm-package/)

**BRVM Data Science** : API yfinance pour BRVM. Fundamentals live (PER/PBR/ROE/ROA/DY), screening dynamique (DY>8%, PER<10...), optimisation Markowitz, backtesting (frais/slippage), CLI sync/live.

## 🚀 Installation

```bash
pip install brvm-package matplotlib  # plot opt
git clone . ; pip install -e .
python -m brvm_package.cli.main sync  # DB live
```

## 🎯 API Complète - Exemple Chaque Commande

### Market
```python
import brvm_package as bv
bv.list_assets()  # ['ABJC', 'BICB', 'SNTS'...]
bv.list_sectors()  # ['Agriculture', 'Services Financiers']
bv.list_countries()  # ['Cote d'Ivoire', 'Senegal']
bv.list_indices(detailed=True)  # pd.DF Benchmark/Sector
bv.market_summary()  # Volume/top gainers
bv.search('bank')  # pd.DF BOA/ECOC
```

### Data/Prix
```python
bv.download('SNTS', '1y')  # OHLCV DF
bv.live_price('SNTS')  # 28500.0
bv.download_all('1mo')  # All
t = bv.Ticker('SNTS')
t.history('5y')  # Full
t.returns(log=True)  # Log returns
t.volatility()  # 25% ann
```

### Fundamentals (PER/PBR...)
```python
bv.valuation_ratios('SNTS')  # PER=7.01 ROE PBR DY=6.1% EPS Beta...
bv.market_cap('BOAC')  # Dict
bv.market_cap_all().head(5)  # Ranked DF weight
bv.dividends('SNTS')  # Hist
bv.financials('SNTS')  # Dict IS/BS/CF DF
bv.fundamental_history('SNTS')  # Time series
bv.shares_outstanding('SNTS')  # 100M
t.financials()  # Same
```

### Screener
```python
bv.screen(sector='Services Financiers', min_dividend_yield=0.05, max_pe=15, sort_by='market_cap')  # 8 banks DF
bv.screen(filters={'roe': ('>',0.1)})  # Custom
bv.screen(min_market_cap=1e12, limit=10)  # Large caps
```

### Portfolio
```python
p = bv.Portfolio(['SNTS','BOAC'])
p.optimize('markowitz')  # Weights optimal
p.performance()  # Sharpe Sortino alpha
p.efficient_frontier(25)  # DF frontier
p.backtest(1e6)  # Report equity_curve
p.plot()  # Equity
p.plot_allocation()  # Pie
```

### Stratégies
```python
bv.momentum_strategy(lookback=60)  # Top movers
bv.value_strategy()  # Low PER high DY
bv.backtest(bv.momentum_strategy(), 1e6)  # Full sim
```

### Analytics
```python
bv.returns_matrix()  # All
bv.correlation_matrix()  # NxN
bv.volatility('SNTS')  # %
bv.beta('BOAC')  # vs market
```

### Macro/FX
```python
bv.fcfa_exchange_rates()  # USD/EUR/XOF
bv.inflation()  # UEMOA
```

### Plot
```python
bv.candlestick('SNTS', '6mo')
bv.heatmap()  # Corr
bv.sector_allocation({'SNTS':0.5})
t.plot()
```

### CLI
```bash
python -m brvm_package.cli.main richbourse  # Live table
python -m brvm_package.cli.main sikafinance SNTS  # JSON PER..
python -m brvm_package.cli.main sync BOAC  # Update
```

## 🏗️ Architecture

```
api/ objects/ analytics/ data/ fundamentals/ plotting/ providers/
```

## Tests

pytest 17/17 | validate_package OK

## MIT Licence
