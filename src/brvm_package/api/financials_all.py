from __future__ import annotations
from pathlib import Path

import pandas as pd

TARGET_YEARS = range(2020, 2026)
MAX_REASONABLE_TOTAL_FCFA = 1e15


def _candidate_paths() -> list[Path]:
    package_root = Path(__file__).resolve().parents[3]
    return [
        package_root / "data" / "brvm_financials_2020_2025_verified.csv",
        package_root / "data" / "brvm_financials_2020_2025_audited.csv",
        package_root / "data" / "brvm_financials_2020_2025.csv",
        package_root / "data" / "brvm_financials_all.csv",
    ]


def _candidate_paths_for_mode(mode: str) -> list[Path]:
    package_root = Path(__file__).resolve().parents[3]
    if mode == "verified":
        return [
            package_root / "data" / "brvm_financials_2020_2025_verified.csv",
            package_root / "data" / "brvm_financials_2020_2025_audited.csv",
            package_root / "data" / "brvm_financials_2020_2025.csv",
            package_root / "data" / "brvm_financials_all.csv",
        ]
    if mode == "audited":
        return [
            package_root / "data" / "brvm_financials_2020_2025_audited.csv",
        ]
    return [
        package_root / "data" / "brvm_financials_2020_2025.csv",
        package_root / "data" / "brvm_financials_all.csv",
        package_root / "data" / "brvm_financials_2020_2025_audited.csv",
        package_root / "data" / "brvm_financials_2020_2025_verified.csv",
    ]


def _normalize_financial_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
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
    if "report_year" not in normalized.columns and "fiscal_year" in normalized.columns:
        normalized["report_year"] = normalized["fiscal_year"]
    if "fiscal_year" in normalized.columns:
        normalized["fiscal_year"] = pd.to_numeric(normalized["fiscal_year"], errors="coerce")
        normalized = normalized[normalized["fiscal_year"].isin(TARGET_YEARS)].copy()
    if "report_year" in normalized.columns:
        normalized["report_year"] = pd.to_numeric(normalized["report_year"], errors="coerce")
    if "publication_date" not in normalized.columns:
        normalized["publication_date"] = pd.NaT
    normalized["publication_date"] = pd.to_datetime(normalized["publication_date"], errors="coerce")
    if "report_year" in normalized.columns:
        missing_report_year = normalized["report_year"].isna()
        normalized.loc[missing_report_year, "report_year"] = normalized.loc[
            missing_report_year, "publication_date"
        ].dt.year
    return normalized


def _apply_quality_filters(dataframe: pd.DataFrame) -> pd.DataFrame:
    filtered = dataframe.copy()
    if "truth_status" in filtered.columns:
        filtered = filtered[filtered["truth_status"] == "verified_like"].copy()
    elif "status" in filtered.columns:
        filtered = filtered[filtered["status"] == "ok"].copy()
    filtered = _drop_suspicious_rows(filtered)
    return filtered


def _drop_suspicious_rows(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe

    filtered = dataframe.copy()
    keep_mask = pd.Series(True, index=filtered.index)

    total_assets = _numeric_series(filtered, "total_actif")
    total_liabilities = _numeric_series(filtered, "dettes_totales")
    equity = _numeric_series(filtered, "capitaux_propres")

    # OCR can occasionally concatenate multiple large values into astronomic numbers.
    if total_assets is not None:
        keep_mask &= total_assets.isna() | (total_assets <= MAX_REASONABLE_TOTAL_FCFA)
    if total_liabilities is not None:
        keep_mask &= total_liabilities.isna() | (total_liabilities <= MAX_REASONABLE_TOTAL_FCFA)

    if total_assets is not None and total_liabilities is not None:
        keep_mask &= (
            total_assets.isna()
            | total_liabilities.isna()
            | (total_liabilities <= (total_assets * 1.2))
        )

    if total_assets is not None and equity is not None:
        keep_mask &= (
            total_assets.isna()
            | equity.isna()
            | (equity <= (total_assets * 1.2))
        )

    return filtered.loc[keep_mask].reset_index(drop=True)


def _numeric_series(dataframe: pd.DataFrame, column: str) -> pd.Series:
    if column not in dataframe.columns:
        return pd.Series(pd.NA, index=dataframe.index, dtype="Float64")
    return pd.to_numeric(dataframe[column], errors="coerce")


def _load_financial_export(mode: str = "verified") -> pd.DataFrame:
    mode = mode.lower()
    if mode not in {"verified", "audited", "all"}:
        raise ValueError("mode must be one of: verified, audited, all")

    for csv_path in _candidate_paths_for_mode(mode):
        if not csv_path.exists():
            continue
        dataframe = _normalize_financial_columns(pd.read_csv(csv_path))
        if mode == "verified":
            dataframe = _apply_quality_filters(dataframe)
        elif mode == "audited":
            if "truth_status" not in dataframe.columns:
                continue
        if {"emetteur", "fiscal_year"}.issubset(dataframe.columns):
            dataframe = dataframe.sort_values(["emetteur", "fiscal_year"]).reset_index(drop=True)
        return dataframe

    searched = ", ".join(str(path) for path in _candidate_paths_for_mode(mode))
    if mode == "audited":
        raise FileNotFoundError(
            f"Aucun export audité trouvé. Chemins cherchés: {searched}. "
            'Lancez "python scripts/audit_financial_truth.py".'
        )
    raise FileNotFoundError(
        f"Aucun export financier trouvé. Chemins cherchés: {searched}. "
        'Lancez "python scripts/extract_brvm_financials.py" ou "python scripts/extract_from_cache.py".'
    )


def financials_all(mode: str = "verified") -> pd.DataFrame:
    """
    Retourne les données financières BRVM extraites des rapports 2020-2025.
    - `verified`: seulement les lignes auditées comme fiables.
    - `audited`: export complet audité avec `truth_status`.
    - `all`: export brut filtré seulement par année.
    """
    return _load_financial_export(mode=mode)


def financials_all_verified() -> pd.DataFrame:
    return _load_financial_export(mode="verified")


def financials_all_audited() -> pd.DataFrame:
    return _load_financial_export(mode="audited")
