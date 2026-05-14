from __future__ import annotations
from pathlib import Path

import pandas as pd

from brvm_package.data.catalog import get_asset_metadata

TARGET_YEARS = range(2020, 2026)
MAX_REASONABLE_TOTAL_FCFA = 1e15
RESOURCE_DIR = Path(__file__).resolve().parents[1] / "resources"
CORE_FIELD_COLUMNS = [
    "resultat_operationnel",
    "resultat_net",
    "chiffre_affaires",
    "capitaux_propres",
    "total_actif",
    "dettes_totales",
    "actifs_courants",
    "passifs_courants",
]
RATIO_FIELD_COLUMNS = [
    "marge_operationnelle",
    "marge_nette",
    "roe",
    "roa",
    "ratio_endettement",
    "autonomie_financiere",
    "ratio_liquidite_generale",
]
FINANCIAL_FIELD_COLUMNS = CORE_FIELD_COLUMNS + RATIO_FIELD_COLUMNS

FINANCIAL_EMITTER_ALIASES = {
    "ABJC": "SERVAIR ABIDJAN CI",
    "BICB": "BIIC",
    "BICC": "BICI CI",
    "BNBC": "BERNABE CI",
    "BOAB": "BANK OF AFRICA BN",
    "BOABF": "BANK OF AFRICA BF",
    "BOAC": "BANK OF AFRICA CI",
    "BOAM": "BANK OF AFRICA ML",
    "BOAN": "BANK OF AFRICA NG",
    "BOAS": "BANK OF AFRICA SN",
    "CABC": "SICABLE",
    "CBIBF": "CORIS BANK INTERNATIONAL",
    "CFAC": "CFAO MOTORS CI",
    "CIEC": "CIE CI",
    "ECOC": "ECOBANK CI",
    "ETIT": "ECOBANK TG",
    "FTSC": "FILTISAC CI",
    "LNBB": "LNB",
    "NEIC": "NEI-CEDA CI",
    "NSBC": "NSBC",
    "NTLC": "NESTLE CI",
    "ONTBF": "ONATEL BF",
    "ORAC": "ORANGE CI",
    "ORGT": "ORAGROUP",
    "PALC": "PALM CI",
    "PRSC": "TRACTAFRIC CI",
    "SAFC": "SAFCA CI",
    "SCRC": "SUCRIVOIRE",
    "SDCC": "SODECI",
    "SDSC": "BOLLORE TRANSPORT & LOGISTICS",
    "SEMC": "CROWN SIEM CI",
    "SGBC": "SGCI",
    "SHEC": "VIVO ENERGY CI",
    "SIBC": "SIB",
    "SICC": "SICOR",
    "SIVC": "SOCIÉTÉ IVOIRIENNE DE RAFFINAGE",
    "SLBC": "SOLIBRA",
    "SMBC": "SMB",
    "SNTS": "SONATEL",
    "SOGC": "SOGB",
    "SPHC": "SAPH CI",
    "STAC": "SETAO CI",
    "STBC": "SITAB",
    "TTLC": "TOTAL",
    "TTLS": "TOTAL SENEGAL S.A.",
    "UNLC": "UNILEVER CI",
    "UNXC": "UNIWAX CI",
}


def _candidate_paths() -> list[Path]:
    package_root = Path(__file__).resolve().parents[3]
    return [
        package_root / "data" / "brvm_financials_2020_2025_reconciled_verified.csv",
        package_root / "data" / "brvm_financials_2020_2025_verified.csv",
        package_root / "data" / "brvm_financials_2020_2025_reconciled_audited.csv",
        package_root / "data" / "brvm_financials_2020_2025_audited.csv",
        package_root / "data" / "brvm_financials_2020_2025.csv",
        package_root / "data" / "brvm_financials_all.csv",
    ]


def _candidate_paths_for_mode(mode: str) -> list[Path]:
    package_root = Path(__file__).resolve().parents[3]
    if mode == "gold":
        return [
            RESOURCE_DIR / "brvm_financials_2020_2025_gold.csv",
            package_root / "data" / "brvm_financials_2020_2025_gold.csv",
        ]
    if mode == "verified":
        return [
            RESOURCE_DIR / "brvm_financials_2020_2025_reconciled_verified.csv",
            RESOURCE_DIR / "brvm_financials_2020_2025_verified.csv",
            package_root / "data" / "brvm_financials_2020_2025_reconciled_verified.csv",
            package_root / "data" / "brvm_financials_2020_2025_verified.csv",
            package_root / "data" / "brvm_financials_2020_2025_reconciled_audited.csv",
            package_root / "data" / "brvm_financials_2020_2025_audited.csv",
            package_root / "data" / "brvm_financials_2020_2025.csv",
            package_root / "data" / "brvm_financials_all.csv",
        ]
    if mode == "usable":
        return [
            RESOURCE_DIR / "brvm_financials_2020_2025_reconciled_audited.csv",
            RESOURCE_DIR / "brvm_financials_2020_2025_audited.csv",
            package_root / "data" / "brvm_financials_2020_2025_reconciled_audited.csv",
            package_root / "data" / "brvm_financials_2020_2025_audited.csv",
            package_root / "data" / "brvm_financials_2020_2025.csv",
            package_root / "data" / "brvm_financials_all.csv",
        ]
    if mode == "audited":
        return [
            RESOURCE_DIR / "brvm_financials_2020_2025_reconciled_audited.csv",
            RESOURCE_DIR / "brvm_financials_2020_2025_audited.csv",
            package_root / "data" / "brvm_financials_2020_2025_reconciled_audited.csv",
            package_root / "data" / "brvm_financials_2020_2025_audited.csv",
        ]
    return [
        RESOURCE_DIR / "brvm_financials_2020_2025_reconciled_audited.csv",
        RESOURCE_DIR / "brvm_financials_2020_2025.csv",
        RESOURCE_DIR / "brvm_financials_all.csv",
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


def _apply_usable_filters(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Keep rows with exploitable statement data while preserving review flags."""
    filtered = dataframe.copy()
    if "status" in filtered.columns:
        filtered = filtered[filtered["status"] == "ok"].copy()
    if "truth_status" in filtered.columns:
        filtered = filtered[filtered["truth_status"].isin(["verified_like", "needs_review"])].copy()
    filtered = _drop_suspicious_rows(filtered)

    available_core_columns = [column for column in CORE_FIELD_COLUMNS if column in filtered.columns]
    if available_core_columns:
        filtered = filtered[filtered[available_core_columns].notna().sum(axis=1) > 0].copy()
    return filtered.reset_index(drop=True)


def _drop_suspicious_rows(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe

    filtered = dataframe.copy()
    keep_mask = pd.Series(True, index=filtered.index)

    total_assets = _numeric_series(filtered, "total_actif")
    total_liabilities = _numeric_series(filtered, "dettes_totales")
    equity = _numeric_series(filtered, "capitaux_propres")
    current_assets = _numeric_series(filtered, "actifs_courants")
    current_liabilities = _numeric_series(filtered, "passifs_courants")

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
    if current_assets is not None:
        keep_mask &= current_assets.isna() | (current_assets >= 0)
    if current_liabilities is not None:
        keep_mask &= current_liabilities.isna() | (current_liabilities >= 0)

    return filtered.loc[keep_mask].reset_index(drop=True)


def _numeric_series(dataframe: pd.DataFrame, column: str) -> pd.Series:
    if column not in dataframe.columns:
        return pd.Series(pd.NA, index=dataframe.index, dtype="Float64")
    return pd.to_numeric(dataframe[column], errors="coerce")


def _load_financial_export(mode: str = "verified") -> pd.DataFrame:
    mode = mode.lower()
    if mode not in {"gold", "verified", "usable", "audited", "all"}:
        raise ValueError("mode must be one of: gold, verified, usable, audited, all")

    for csv_path in _candidate_paths_for_mode(mode):
        if not csv_path.exists():
            continue
        dataframe = _normalize_financial_columns(pd.read_csv(csv_path))
        if mode == "verified":
            dataframe = _apply_quality_filters(dataframe)
        elif mode == "usable":
            dataframe = _apply_usable_filters(dataframe)
        elif mode == "audited":
            if "truth_status" not in dataframe.columns:
                continue
        dataframe = _annotate_data_presence(dataframe)
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
    - `gold`: sous-ensemble publication-ready haute confiance.
    - `verified`: seulement les lignes auditées comme fiables.
    - `usable`: lignes exploitables avec données financières, y compris à revoir.
    - `audited`: export complet audité avec `truth_status`.
    - `all`: export brut filtré seulement par année.
    """
    return _load_financial_export(mode=mode)


def financials_all_gold() -> pd.DataFrame:
    return _load_financial_export(mode="gold")


def financials_all_verified() -> pd.DataFrame:
    return _load_financial_export(mode="verified")


def financials_all_usable() -> pd.DataFrame:
    return _load_financial_export(mode="usable")


def financials_all_audited() -> pd.DataFrame:
    return _load_financial_export(mode="audited")


def financial_statements(
    symbol_or_name: str,
    years: list[int] | None = None,
    mode: str = "audited",
) -> pd.DataFrame:
    """
    Retourne les états financiers BRVM 2020-2025 pour une société.

    `mode="audited"` est volontairement le défaut: il renvoie aussi les lignes
    `missing_report` et `needs_review`, avec leur statut et leur URL source.
    Utilisez `mode="usable"` pour récupérer toutes les lignes exploitables avec
    leurs alertes, ou `mode="verified"` / `mode="gold"` pour ne récupérer que les
    lignes publiables selon les filtres qualité.
    """
    frame = _load_financial_export(mode=mode)
    matched = _filter_financial_rows(frame, symbol_or_name)
    if years is not None and "fiscal_year" in matched.columns:
        matched = matched[matched["fiscal_year"].isin(years)].copy()
    return _order_financial_statement_columns(matched)


def financial_statement_status(
    symbol_or_name: str | None = None,
    years: list[int] | None = None,
) -> dict[str, object]:
    """
    Diagnostic de vérité/couverture pour une société ou pour tout l'univers suivi.

    Cette fonction ne remplace pas les valeurs manquantes: elle expose les trous.
    C'est l'API à utiliser avant de publier une analyse qui exige zéro ambiguïté.
    """
    target_years = list(years or TARGET_YEARS)
    audited = _load_financial_export(mode="audited")
    scoped = _filter_financial_rows(audited, symbol_or_name) if symbol_or_name else audited.copy()
    if "fiscal_year" in scoped.columns:
        scoped = scoped[scoped["fiscal_year"].isin(target_years)].copy()

    if symbol_or_name:
        expected_rows = len(target_years)
    else:
        expected_rows = int(audited["emetteur"].dropna().nunique() * len(target_years))

    truth_counts = (
        scoped["truth_status"].fillna("NA").value_counts().sort_index().to_dict()
        if "truth_status" in scoped.columns
        else {}
    )
    status_counts = (
        scoped["status"].fillna("NA").value_counts().sort_index().to_dict()
        if "status" in scoped.columns
        else {}
    )
    years_tracked = _unique_years(scoped)
    verified_years = _unique_years(scoped[scoped.get("truth_status", pd.Series(dtype="object")).eq("verified_like")])
    review_years = _unique_years(scoped[scoped.get("truth_status", pd.Series(dtype="object")).eq("needs_review")])
    missing_years = [year for year in target_years if year not in years_tracked]
    years_without_verified_data = [year for year in target_years if year not in verified_years]

    rows_with_any_financial_data = 0
    if all(column in scoped.columns for column in CORE_FIELD_COLUMNS):
        rows_with_any_financial_data = int((scoped[CORE_FIELD_COLUMNS].notna().sum(axis=1) > 0).sum())

    return {
        "query": symbol_or_name,
        "mode": "audited",
        "years_expected": target_years,
        "rows_expected": expected_rows,
        "rows_tracked": int(len(scoped)),
        "rows_with_any_financial_data": rows_with_any_financial_data,
        "verified_rows": int((scoped.get("truth_status", pd.Series(dtype="object")) == "verified_like").sum()),
        "review_rows": int((scoped.get("truth_status", pd.Series(dtype="object")) == "needs_review").sum()),
        "missing_or_error_rows": int((scoped.get("truth_status", pd.Series(dtype="object")) == "missing_or_error").sum()),
        "years_tracked": years_tracked,
        "verified_years": verified_years,
        "review_years": review_years,
        "missing_years": missing_years,
        "years_without_verified_data": years_without_verified_data,
        "tracking_complete": len(missing_years) == 0,
        "verified_complete": len(years_without_verified_data) == 0,
        "truth_counts": {str(key): int(value) for key, value in truth_counts.items()},
        "status_counts": {str(key): int(value) for key, value in status_counts.items()},
    }


def financials_coverage_report(mode: str = "verified") -> pd.DataFrame:
    """
    Résume la couverture 2020-2025 par émetteur.

    Colonnes:
    - `emetteur`
    - `years_tracked`
    - `missing_tracked_years`
    - `rows_tracked`
    - `years_with_financial_data`
    - `missing_data_years`
    - `rows_with_financial_data`
    - `rows_expected`
    - `tracking_complete`
    - `data_complete`
    """
    frame = _load_financial_export(mode=mode)
    universe = _load_financial_export(mode="all")
    target_years = list(TARGET_YEARS)
    target_emetteurs = sorted(universe["emetteur"].dropna().unique().tolist())

    rows: list[dict[str, object]] = []
    for emetteur in target_emetteurs:
        emitter_frame = frame[frame["emetteur"] == emetteur].copy()
        years_tracked = sorted(
            int(year) for year in emitter_frame["fiscal_year"].dropna().astype(int).unique().tolist()
        )
        data_frame = emitter_frame[emitter_frame["has_financial_data"]].copy()
        years_with_financial_data = sorted(
            int(year) for year in data_frame["fiscal_year"].dropna().astype(int).unique().tolist()
        )
        missing_tracked_years = [year for year in target_years if year not in years_tracked]
        missing_data_years = [year for year in target_years if year not in years_with_financial_data]
        rows.append(
            {
                "emetteur": emetteur,
                "years_tracked": years_tracked,
                "missing_tracked_years": missing_tracked_years,
                "rows_tracked": len(years_tracked),
                "years_with_financial_data": years_with_financial_data,
                "missing_data_years": missing_data_years,
                "rows_with_financial_data": len(years_with_financial_data),
                "rows_expected": len(target_years),
                "tracking_complete": len(missing_tracked_years) == 0,
                "data_complete": len(missing_data_years) == 0,
            }
        )

    return pd.DataFrame(rows).sort_values(["data_complete", "emetteur"], ascending=[True, True]).reset_index(drop=True)


def financials_coverage_summary(mode: str = "verified") -> dict[str, object]:
    """
    Retourne un résumé compact de la couverture de l'export financier 2020-2025.
    """
    frame = _load_financial_export(mode=mode)
    universe = _load_financial_export(mode="all")
    coverage = financials_coverage_report(mode=mode)

    status_counts = (
        frame["status"].fillna("NA").value_counts().sort_index().to_dict()
        if "status" in frame.columns
        else {}
    )
    truth_counts = (
        frame["truth_status"].fillna("NA").value_counts().sort_index().to_dict()
        if "truth_status" in frame.columns
        else {}
    )
    yearly_counts = {
        int(year): int(count)
        for year, count in frame.groupby("fiscal_year").size().sort_index().items()
    }

    rows_expected = int(universe["emetteur"].dropna().nunique() * len(TARGET_YEARS))
    missing_core_distribution = (
        frame[CORE_FIELD_COLUMNS].isna().sum(axis=1).value_counts().sort_index().to_dict()
        if all(column in frame.columns for column in CORE_FIELD_COLUMNS)
        else {}
    )

    rows_with_financial_data = int(frame["has_financial_data"].sum()) if "has_financial_data" in frame.columns else 0
    incomplete = coverage[~coverage["data_complete"]]
    return {
        "mode": mode,
        "rows": int(len(frame)),
        "rows_expected": rows_expected,
        "tracking_coverage_ratio": (len(frame) / rows_expected) if rows_expected else None,
        "rows_with_financial_data": rows_with_financial_data,
        "data_coverage_ratio": (rows_with_financial_data / rows_expected) if rows_expected else None,
        "emitters_total": int(universe["emetteur"].dropna().nunique()),
        "emitters_with_rows": int(frame["emetteur"].dropna().nunique()),
        "emitters_tracking_complete": int(coverage["tracking_complete"].sum()),
        "emitters_data_complete": int(coverage["data_complete"].sum()),
        "emitters_incomplete": int((~coverage["data_complete"]).sum()),
        "yearly_counts": yearly_counts,
        "status_counts": status_counts,
        "truth_counts": truth_counts,
        "missing_core_distribution": {int(key): int(value) for key, value in missing_core_distribution.items()},
        "sample_incomplete_emitters": incomplete["emetteur"].head(10).tolist(),
    }


def _annotate_data_presence(dataframe: pd.DataFrame) -> pd.DataFrame:
    annotated = dataframe.copy()
    core_columns = [column for column in CORE_FIELD_COLUMNS if column in annotated.columns]
    if not core_columns:
        annotated["core_metrics_present"] = 0
        annotated["has_financial_data"] = False
        return annotated

    annotated["core_metrics_present"] = annotated[core_columns].notna().sum(axis=1)
    annotated["has_financial_data"] = (
        annotated["core_metrics_present"] > 0
    ) & annotated.get("status", pd.Series(index=annotated.index, dtype="object")).fillna("").ne("missing_report")
    return annotated


def _filter_financial_rows(dataframe: pd.DataFrame, symbol_or_name: str) -> pd.DataFrame:
    if dataframe.empty or "emetteur" not in dataframe.columns:
        return dataframe.copy()

    query = symbol_or_name.strip()
    if not query:
        return dataframe.iloc[0:0].copy()

    emitter = _resolve_emitter_name(query, dataframe)
    normalized_query = _normalize_lookup_text(emitter or query)
    normalized_emitters = dataframe["emetteur"].fillna("").map(_normalize_lookup_text)

    exact = dataframe[normalized_emitters == normalized_query].copy()
    if not exact.empty:
        return exact

    contains = dataframe[
        normalized_emitters.map(lambda value: normalized_query in value or value in normalized_query)
    ].copy()
    return contains


def _resolve_emitter_name(query: str, dataframe: pd.DataFrame) -> str | None:
    normalized_symbol = query.upper()
    if normalized_symbol in FINANCIAL_EMITTER_ALIASES:
        return FINANCIAL_EMITTER_ALIASES[normalized_symbol]

    metadata = get_asset_metadata(normalized_symbol)
    if metadata:
        catalog_name = _normalize_lookup_text(metadata.get("name", ""))
        emitter_names = dataframe["emetteur"].dropna().astype(str).unique().tolist()
        scored: list[tuple[int, str]] = []
        catalog_tokens = set(catalog_name.split())
        for emitter_name in emitter_names:
            emitter_tokens = set(_normalize_lookup_text(emitter_name).split())
            overlap = len(catalog_tokens & emitter_tokens)
            if overlap:
                scored.append((overlap, emitter_name))
        if scored:
            return sorted(scored, key=lambda item: (-item[0], item[1]))[0][1]

    return None


def _normalize_lookup_text(value: str) -> str:
    import re
    import unicodedata

    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _order_financial_statement_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    ordered = [
        "emetteur",
        "fiscal_year",
        "report_year",
        "publication_date",
        "status",
        "truth_status",
        "truth_reason",
        "status_reason",
        "diagnostic",
        "core_metrics_count",
        *FINANCIAL_FIELD_COLUMNS,
        "report_title",
        "report_url",
        "company_url",
    ]
    existing = [column for column in ordered if column in dataframe.columns]
    remaining = [column for column in dataframe.columns if column not in existing]
    return dataframe[existing + remaining].reset_index(drop=True)


def _unique_years(dataframe: pd.DataFrame) -> list[int]:
    if dataframe.empty or "fiscal_year" not in dataframe.columns:
        return []
    return sorted(
        int(year)
        for year in pd.to_numeric(dataframe["fiscal_year"], errors="coerce").dropna().unique().tolist()
    )
