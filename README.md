# brvm-package [![Tests: 47 passed](https://img.shields.io/badge/tests-47%20passed-brightgreen) [![PyPI](https://badge.fury.io/py/brvm-package.svg)](https://pypi.org/project/brvm-package/)

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

### Etats financiers BRVM 2020-2025
```python
# Toutes les lignes suivies: 73 emetteurs x 6 exercices = 438 lignes.
# Inclut les statuts missing_report / needs_review / verified_like.
bv.financials_all(mode="audited")

# Sous-ensemble fiable par defaut: lignes verifiees seulement.
bv.financials_all(mode="verified")

# Sous-ensemble publication-ready plus strict.
bv.financials_all_gold()

# Etats financiers d'une societe par symbole BRVM ou nom.
bv.financial_statements("SNTS", mode="audited")
bv.financial_statements("BOAB", years=[2021, 2022], mode="verified")

# Diagnostic avant publication: ne masque jamais les trous.
bv.financial_statement_status("SNTS")
bv.financials_coverage_summary()
```

Les colonnes incluent les 15 indicateurs demandes: resultat operationnel, resultat net,
chiffre d'affaires, capitaux propres, total actif, dettes totales, actifs/passifs courants,
marges, ROE, ROA, endettement, autonomie financiere et liquidite generale. Les lignes
non verifiees restent accessibles en `mode="audited"`, mais ne sont pas presentees
comme vraies sans leur `truth_status`, `status_reason`, `diagnostic` et `report_url`.

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

pytest: 47 passed, 9 live tests opt-in.

## MIT Licence
