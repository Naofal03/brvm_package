# Financials Publication Report

This report is the publication truth source for packaged BRVM financial-report coverage.

## Publication policy

- `gold`: `status=ok`, `truth_status=verified_like`, at least 7/8 core fields, no suspicious profitability/accounting flags, balance-sheet gap <= 10% when checkable.
- `review`: parsed rows worth manual truth-checking before public claims.
- `exclude`: missing/error rows or rows too weak for publication.

## Coverage snapshot

- Rows expected in 2020-2025 window: 438
- Audited tracking rows: 438
- Gold rows: 102
- Review candidates: 36
- Gold coverage ratio: 23.29%
- Audited emitters: 73
- Gold emitters: 35
- Emitters complete on all 2020-2025 years in gold: 2
- Emitters complete on all 2020-2025 years in review+gold: 3

## Gold rows by fiscal year

- 2020: 18
- 2021: 21
- 2022: 22
- 2023: 16
- 2024: 16
- 2025: 9

## Emitters with incomplete gold coverage

- BANK OF AFRICA BF: missing 2020, 2025
- BANK OF AFRICA BN: missing 2020, 2023, 2024
- BANK OF AFRICA CI: missing 2021, 2025
- BANK OF AFRICA ML: missing 2022, 2023, 2024
- BANK OF AFRICA NG: missing 2020, 2022, 2023, 2024, 2025
- BANK OF AFRICA SN: missing 2023, 2024, 2025
- BERNABE CI: missing 2021, 2022, 2023, 2024, 2025
- BICI CI: missing 2020
- BIIC: missing 2020, 2021, 2022, 2023, 2025
- CFAO MOTORS CI: missing 2023, 2025
- CORIS BANK INTERNATIONAL: missing 2020, 2021, 2023, 2024, 2025
- CROWN SIEM CI: missing 2024, 2025
- ECOBANK CI: missing 2021, 2022, 2024, 2025
- ECOBANK TG: missing 2020, 2022, 2025
- FILTISAC CI: missing 2020, 2021, 2023, 2025
- NSBC: missing 2025
- ONATEL BF: missing 2020, 2025
- PALM CI: missing 2023
- SAFCA CI: missing 2022, 2023, 2025
- SAPH CI: missing 2020, 2021, 2022, 2024, 2025
- SERVAIR ABIDJAN CI: missing 2020, 2023, 2024
- SIB: missing 2021, 2022, 2023, 2024, 2025
- SICABLE: missing 2020, 2022, 2023, 2024, 2025
- SICOR: missing 2021, 2022, 2023, 2024, 2025
- SITAB: missing 2020, 2021, 2023, 2024, 2025
- SMB: missing 2025
- SODECI: missing 2020, 2021, 2023, 2024
- SOGB: missing 2020, 2022, 2024, 2025
- SOLIBRA: missing 2024, 2025
- SUCRIVOIRE: missing 2020, 2021, 2023, 2024, 2025
- TOTAL: missing 2022
- TRACTAFRIC CI: missing 2020, 2021, 2025
- UNIWAX CI: missing 2021, 2023, 2024, 2025

## Top review candidates

```text
                     emetteur  fiscal_year  truth_status  core_metrics_present suspicious_flags status_reason
            BANK OF AFRICA BF         2020 verified_like                     5                            NaN
            BANK OF AFRICA SN         2025 verified_like                     6                            NaN
                   BERNABE CI         2021 verified_like                     8      extreme_roe           NaN
                   BERNABE CI         2024 verified_like                     8      extreme_roe           NaN
BOLLORE TRANSPORT & LOGISTICS         2023 verified_like                     8      extreme_roe           NaN
                       CIE CI         2020 verified_like                     6                            NaN
                   ECOBANK CI         2021 verified_like                     6                            NaN
                   ECOBANK CI         2022 verified_like                     6                            NaN
                  FILTISAC CI         2021  needs_review                     7                            NaN
                    NESTLE CI         2020 verified_like                     8      extreme_roe           NaN
                    NESTLE CI         2023 verified_like                     7      extreme_roe           NaN
                    ONATEL BF         2025  needs_review                     8                            NaN
                     ORAGROUP         2022 verified_like                     5                            NaN
                     ORAGROUP         2023 verified_like                     5                            NaN
                    ORANGE CI         2022  needs_review                     8                            NaN
                    ORANGE CI         2023  needs_review                     8                            NaN
                    ORANGE CI         2024  needs_review                     8                            NaN
                    ORANGE CI         2025  needs_review                     8                            NaN
                      SAPH CI         2020 verified_like                     8      extreme_roe           NaN
                      SAPH CI         2021 verified_like                     8      extreme_roe           NaN
                      SAPH CI         2022 verified_like                     8      extreme_roe           NaN
                      SAPH CI         2024 verified_like                     8      extreme_roe           NaN
                      SAPH CI         2025 verified_like                     8      extreme_roe           NaN
           SERVAIR ABIDJAN CI         2020  needs_review                     7                            NaN
                         SGCI         2021 verified_like                     5                            NaN
                       SODECI         2020 verified_like                     8      extreme_roe           NaN
                       SODECI         2021  needs_review                     7                            NaN
                       SODECI         2023  needs_review                     8                            NaN
                         SOGB         2020 verified_like                     6      extreme_roe           NaN
                         SOGB         2022 verified_like                     7      extreme_roa           NaN
```
