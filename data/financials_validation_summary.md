# Validation Summary

Date: 2026-05-06

## Dataset status

- Audited rows: 438
- Verified rows: 122
- Audited emitters: 73
- Verified emitters: 39
- Emitters with zero verified rows: 34
- Emitters with incomplete `2020-2025` coverage despite at least one verified row: 36

## Coverage by fiscal year

| Fiscal year | Verified rows |
| --- | ---: |
| 2020 | 24 |
| 2021 | 25 |
| 2022 | 24 |
| 2023 | 19 |
| 2024 | 19 |
| 2025 | 11 |

## Core-field completeness

Core fields checked:

- `resultat_operationnel`
- `resultat_net`
- `chiffre_affaires`
- `capitaux_propres`
- `total_actif`
- `dettes_totales`
- `actifs_courants`
- `passifs_courants`

Distribution of missing core fields per verified row:

| Missing core fields | Rows |
| --- | ---: |
| 0 | 59 |
| 1 | 54 |
| 2 | 5 |
| 3 | 4 |

## Accounting consistency

- Rows checked with `total_actif`, `capitaux_propres`, `dettes_totales`: 119
- Rows with balance-sheet identity gap `<= 1%`: 96
- Rows with balance-sheet identity gap `<= 5%`: 112
- Rows with balance-sheet identity gap `<= 10%`: 119
- Stored ratios match the current pipeline formulas on all verified rows: 0 mismatches

Interpretation:

- The raw extracted values are mostly self-consistent.
- The current weak point is coverage, not internal recomputation.
- Some extreme profitability ratios remain suspicious and should be manually reviewed.

## Emitters with zero verified rows

- AIR LIQUIDE CI
- BBGCI
- COTE D'IVOIRE TELECOM
- DC/BR
- EDKSN
- FCTC SONATEL
- FCTCEPT
- FCTCSNTS
- FIDELIS FINANCE
- FIMSN.O1
- FOCUS IMMOBILIER SA
- LNB
- MOVIS CI
- NOURMONY HOLDING
- ORANGE CI
- SANCFIS FASO SA
- SDMA S.A
- SICABLE
- SIMPA SA
- SITAB
- SOCIÉTÉ IVOIRIENNE DE RAFFINAGE
- SONATEL
- TEYLIMOGPCI
- TNC_FIDFIN.O1
- TNC_NMHGCINC.O1
- TNC_SCFBF.O1
- TNC_SDMACI.O1
- TNC_SIMPSNNC.O1
- TOTAL SENEGAL S.A.
- TPBF
- TPBJ
- TPCI
- TRITRAF CI
- VIVO ENERGY CI

## Suspicious verified rows to review

- BERNABE CI 2021: extreme ROE
- BERNABE CI 2024: extreme ROE
- BOLLORE TRANSPORT & LOGISTICS 2023: extreme ROE
- NESTLE CI 2020: extreme ROE
- NESTLE CI 2023: extreme ROE
- SAPH CI 2020: extreme ROE
- SAPH CI 2021: extreme ROE
- SAPH CI 2022: extreme ROE
- SAPH CI 2024: extreme ROE
- SAPH CI 2025: extreme ROE
- SODECI 2020: extreme ROE
- SOGB 2020: extreme ROE
- SOGB 2022: extreme ROA
- SOGB 2024: extreme ROE and extreme ROA
- UNILEVER CI 2021: extreme ROE

## Worst balance-sheet gaps

These rows still remain under the `10%` tolerance but are the highest-gap records and should be prioritized for manual truth-checking:

- TRACTAFRIC CI 2022
- ECOBANK TG 2021
- TOTAL 2020
- TRACTAFRIC CI 2023
- ECOBANK TG 2024
- ECOBANK TG 2023
- SODECI 2020

## Recommended interpretation

- The current verified dataset is usable as a partial high-confidence base.
- It is not yet a complete `all BRVM equities 2020-2025` dataset.
- For downstream use, trust raw statement fields first.
- Derived ratios are consistent with the implemented formulas, but some economically extreme rows still need manual validation from source documents.
