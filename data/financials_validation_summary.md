# Validation Summary

Date: 2026-05-14

## Dataset status

- Audited rows: 438
- Verified rows in reconciled source: 120
- Verified rows exposed by `brvm.financials_all()`: 120 after package quality filters
- Usable rows exposed by `brvm.financials_all_usable()`: 180
- Audited emitters: 73
- Verified emitters: 42
- Usable emitters: 46
- Emitters with zero verified rows in default API output: 31
- Emitters with complete `2020-2025` verified coverage: 2
- Emitters with incomplete `2020-2025` verified coverage: 71

## Coverage by fiscal year

| Fiscal year | Verified rows |
| --- | ---: |
| 2020 | 22 |
| 2021 | 24 |
| 2022 | 25 |
| 2023 | 17 |
| 2024 | 21 |
| 2025 | 11 |

## 2025 status

- Audited 2025 rows tracked: 73
- 2025 rows with an extracted report: 32
- 2025 rows still missing/error: 41
- 2025 rows requiring manual review: 21
- 2025 rows exposed as verified by the default API: 11
- 2025 rows exposed as usable with diagnostics: 26

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
| 1 | 49 |
| 2 | 5 |
| 3 | 7 |

## Accounting consistency

- Rows checked with `total_actif`, `capitaux_propres`, `dettes_totales`: 113
- Rows with balance-sheet identity gap `<= 1%`: 92
- Rows with balance-sheet identity gap `<= 5%`: 106
- Rows with balance-sheet identity gap `<= 10%`: 113
- Stored ratios match the current pipeline formulas on all verified rows: 0 mismatches

Interpretation:

- The raw extracted values are mostly self-consistent.
- The current weak point is coverage, not internal recomputation.
- Some extreme profitability ratios remain suspicious and should be manually reviewed.
- Astronomic OCR values and negative current assets/liabilities are excluded from the verified exports.

## Emitters with zero verified rows in default API output

- AIR LIQUIDE CI
- BANK OF AFRICA NG
- BBGCI
- BOLLORE TRANSPORT & LOGISTICS
- CIE CI
- COTE D'IVOIRE TELECOM
- DC/BR
- EDKSN
- FCTC SONATEL
- FCTCEPT
- FCTCSNTS
- FIDELIS FINANCE
- FIMSN.O1
- FOCUS IMMOBILIER SA
- MOVIS CI
- NOURMONY HOLDING
- SANCFIS FASO SA
- SDMA S.A
- SIMPA SA
- SOCIÉTÉ IVOIRIENNE DE RAFFINAGE
- TEYLIMOGPCI
- TNC_FIDFIN.O1
- TNC_NMHGCINC.O1
- TNC_SCFBF.O1
- TNC_SDMACI.O1
- TNC_SIMPSNNC.O1
- TPBF
- TPBJ
- TPCI
- TRITRAF CI
- VIVO ENERGY CI

## Suspicious rows in reconciled source to review

- BERNABE CI 2021: extreme ROE
- BERNABE CI 2024: extreme ROE
- NESTLE CI 2020: extreme ROE
- NESTLE CI 2023: extreme ROE
- SAPH CI 2020: extreme ROE
- SAPH CI 2021: extreme ROE
- SAPH CI 2022: extreme ROE
- SAPH CI 2024: extreme ROE
- SGCI 2025: extreme operating margin
- SODECI 2020: extreme ROE
- SOGB 2020: extreme ROE
- SOGB 2022: extreme ROA
- SOGB 2024: extreme ROE and extreme ROA
- SONATEL 2025: extreme ROE
- UNILEVER CI 2021: extreme ROE

## Worst balance-sheet gaps

These rows still remain under the `10%` tolerance but are the highest-gap records and should be prioritized for manual truth-checking:

- TRACTAFRIC CI 2022
- ECOBANK TG 2021
- PALM CI 2025
- TOTAL 2020
- ECOBANK TG 2024
- ECOBANK TG 2023
- SODECI 2020

## Recommended interpretation

- The current verified dataset is usable as a partial high-confidence base.
- The usable dataset exposes more exploitable rows while retaining review flags and source URLs.
- It is not yet a complete `all BRVM equities 2020-2025` dataset.
- For downstream use, trust raw statement fields first.
- Derived ratios are consistent with the implemented formulas, but some economically extreme rows still need manual validation from source documents.
