# Plan d'Implémentation BRVM Package - Amélioration Données Financières (2020-2025)

**Contexte du Projet** : Travail dans `/Users/naofal/Desktop/brvm_package`. Structure modulaire yfinance-like déjà présente. Données 2020-2025 dans `data/brvm_financials_2020_2025.csv` avec métriques exactes demandées.

**État Actuel** :
- Parser PDF extrait : Résultat opérationnel/net, CA, capitaux propres, total actif, dettes, etc. + ratios auto-calculés.
- `Ticker.financials()` retourne DataFrames.
- Couverture : ~80% entreprises, quelques gaps (missing_report).

**Objectif** : Filtre 2020-2025 dans API/Ticker, exposition complète, robustesse.

## Étapes Détaillées (À cocher)

### 1. ✅ Création TODO_FINANCIALS_FR.md (cette étape)

### 2. 🔄 Amélioration ticker.py & core.py (filtrage years en cours)
```
- Ajouter param `years: list[int] = [2020,2021,2022,2023,2024,2025]`
- Filtrer DataFrame par fiscal_year
- Retourner dict : {'income_statement': df, 'balance_sheet': df, 'ratios': df}
```
**Test** : `bv.Ticker('BOABF').financials([2020,2023])`

### 3. Ajouter `src/brvm_package/fundamentals/core.py` (filtrage)
```
def financials(symbol: str, years: list[int]) -> dict:
    df = pd.read_csv('data/brvm_financials_2020_2025.csv')
    df = df[df['emetteur'].str.contains(symbol.upper()) & df['fiscal_year'].isin(years)]
    # Pivot/group par métrique
    return {'income': ..., 'ratios': ...}
```

### 4. `src/brvm_package/api/fundamentals.py`
```
- Ajouter financials_all(years=[2020,2025]) → CSV complet filtré
- Exposer brvm.financials("SNTS", years=[2020,2025])
```

### 5. Robustesse scraper `financial_reports/scraper.py`
```
- Ajouter tenacity/retry(3) sur BRVM requests
- Logs rich.print pour diagnostics
```

### 6. Tests & Validation
```
cd /Users/naofal/Desktop/brvm_package
pip install -e .
pytest tests/test_financial_reports_support.py -v
python -c "import brvm as bv; print(bv.financials_all([2020]))"
brvm sync-financials  # si CLI existe
python scripts/validate_financials_coverage.py
```

### 7. Documentation
```
- README.md : Exemples Ticker.financials()
- Coverage : Viser 90% entreprises 2020-2025
```

## Priorités Immédiates
1. Étape 2 : ticker.py (20min)
2. Étape 3-4 : API (15min)
3. Tests (10min)
4. attempt_completion

**Prochaines Étapes après** : Portfolio analytics, screener.

**Status** : Prêt pour implémentation BLACKBOXAI. Cocher au fur et à mesure.

