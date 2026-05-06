#!/usr/bin/env python3
"""Validate BRVM financial export coverage for the 2020-2025 target window."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

TARGET_YEARS = list(range(2020, 2026))
CSV_CANDIDATES = [
    Path("data/brvm_financials_2020_2025.csv"),
    Path("data/brvm_financials_all.csv"),
]
CORE_FIELDS = [
    "resultat_operationnel",
    "resultat_net",
    "chiffre_affaires",
    "capitaux_propres",
    "total_actif",
    "dettes_totales",
    "actifs_courants",
    "passifs_courants",
]


def resolve_csv_path() -> Path:
    for path in CSV_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Aucun export financier trouvé. Fichiers attendus: "
        + ", ".join(str(path) for path in CSV_CANDIDATES)
    )


def normalize_fiscal_year(dataframe: pd.DataFrame) -> pd.DataFrame:
    normalized = dataframe.copy()
    if "fiscal_year" not in normalized.columns:
        fiscal_year = None
        if "report_title" in normalized.columns:
            extracted = normalized["report_title"].fillna("").str.extract(
                r"(?i)(?:exercice|au\s+31\s+decembre|etats?\s+financiers?|comptes?).*?(20\d{2})",
                expand=False,
            )
            fiscal_year = pd.to_numeric(extracted, errors="coerce")
        if fiscal_year is None and "report_url" in normalized.columns:
            extracted = normalized["report_url"].fillna("").str.extract(r"(20\d{2})", expand=False)
            fiscal_year = pd.to_numeric(extracted, errors="coerce") - 1
        if fiscal_year is None and "report_year" in normalized.columns:
            fiscal_year = pd.to_numeric(normalized["report_year"], errors="coerce")
        if fiscal_year is not None:
            normalized["fiscal_year"] = fiscal_year
    normalized["fiscal_year"] = pd.to_numeric(normalized["fiscal_year"], errors="coerce")
    return normalized


def main() -> None:
    csv_path = resolve_csv_path()
    dataframe = normalize_fiscal_year(pd.read_csv(csv_path))
    scoped = dataframe[dataframe["fiscal_year"].isin(TARGET_YEARS)].copy()

    print(f"Source: {csv_path}")
    print(f"Rows in target window: {len(scoped)}")
    print(f"Emitters in target window: {scoped['emetteur'].nunique() if 'emetteur' in scoped.columns else 0}")

    if scoped.empty:
        return

    if "status" in scoped.columns:
        print("\nStatus counts:")
        print(scoped["status"].value_counts(dropna=False).to_string())

    ok_rows = scoped[scoped.get("status", "ok") == "ok"].copy()
    if ok_rows.empty:
        print("\nNo OK rows found in target window.")
        return

    missing_rows = []
    completeness_rows = []
    for emetteur, emitter_frame in ok_rows.groupby("emetteur"):
        years = sorted(emitter_frame["fiscal_year"].dropna().astype(int).unique().tolist())
        missing_years = [year for year in TARGET_YEARS if year not in years]
        if missing_years:
            missing_rows.append({"emetteur": emetteur, "missing_years": ",".join(str(year) for year in missing_years)})
        for _, row in emitter_frame.iterrows():
            available_core_fields = sum(pd.notna(row.get(field)) for field in CORE_FIELDS)
            completeness_rows.append(
                {
                    "emetteur": emetteur,
                    "fiscal_year": int(row["fiscal_year"]),
                    "available_core_fields": available_core_fields,
                    "missing_core_fields": len(CORE_FIELDS) - available_core_fields,
                }
            )

    if missing_rows:
        print("\nEmitter/year gaps:")
        print(pd.DataFrame(missing_rows).sort_values("emetteur").to_string(index=False))

    completeness = pd.DataFrame(completeness_rows).sort_values(
        ["missing_core_fields", "emetteur", "fiscal_year"],
        ascending=[False, True, True],
    )
    print("\nLowest-completeness rows:")
    print(completeness.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
