#!/usr/bin/env python3
"""Build publication-ready BRVM financial datasets and report."""
from __future__ import annotations

from pathlib import Path
import shutil

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RESOURCES_DIR = ROOT / "src" / "brvm_package" / "resources"

AUDITED_PATH = DATA_DIR / "brvm_financials_2020_2025_audited.csv"
RECONCILED_AUDITED_PATH = DATA_DIR / "brvm_financials_2020_2025_reconciled_audited.csv"
VERIFIED_PATH = DATA_DIR / "brvm_financials_2020_2025_verified.csv"
GOLD_PATH = DATA_DIR / "brvm_financials_2020_2025_gold.csv"
REVIEW_PATH = DATA_DIR / "brvm_financials_2020_2025_review_candidates.csv"
REPORT_PATH = DATA_DIR / "financials_publication_report.md"
PACKAGED_GOLD_PATH = RESOURCES_DIR / "brvm_financials_2020_2025_gold.csv"
PACKAGED_REPORT_PATH = RESOURCES_DIR / "financials_publication_report.md"

TARGET_YEARS = list(range(2020, 2026))
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
ALL_FIELDS = CORE_FIELDS + [
    "marge_operationnelle",
    "marge_nette",
    "roe",
    "roa",
    "ratio_endettement",
    "autonomie_financiere",
    "ratio_liquidite_generale",
]


def _load(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required input: {path}")
    frame = pd.read_csv(path)
    frame["fiscal_year"] = pd.to_numeric(frame["fiscal_year"], errors="coerce")
    return frame[frame["fiscal_year"].isin(TARGET_YEARS)].copy()


def _balance_sheet_gap_pct(frame: pd.DataFrame) -> pd.Series:
    complete = frame[["total_actif", "capitaux_propres", "dettes_totales"]].notna().all(axis=1)
    result = pd.Series(pd.NA, index=frame.index, dtype="Float64")
    result.loc[complete] = (
        (frame.loc[complete, "total_actif"] - (frame.loc[complete, "capitaux_propres"] + frame.loc[complete, "dettes_totales"])).abs()
        / frame.loc[complete, "total_actif"].abs().replace(0, pd.NA)
    )
    return result


def _suspicious_flags(row: pd.Series) -> str:
    issues: list[str] = []
    equity = row.get("capitaux_propres")
    total_assets = row.get("total_actif")
    total_debts = row.get("dettes_totales")
    revenue = row.get("chiffre_affaires")
    operating_income = row.get("resultat_operationnel")
    net_income = row.get("resultat_net")

    if pd.notna(equity) and float(equity) <= 0:
        issues.append("non_positive_equity")
    if pd.notna(total_assets) and float(total_assets) <= 0:
        issues.append("non_positive_total_assets")
    if pd.notna(total_debts) and float(total_debts) < 0:
        issues.append("negative_total_debts")
    if pd.notna(revenue) and pd.notna(operating_income) and float(revenue) != 0:
        if abs(float(operating_income) / float(revenue)) > 1.2:
            issues.append("extreme_operating_margin")
    if pd.notna(revenue) and pd.notna(net_income) and float(revenue) != 0:
        if abs(float(net_income) / float(revenue)) > 1.2:
            issues.append("extreme_net_margin")
    if pd.notna(equity) and pd.notna(net_income) and float(equity) != 0:
        if abs(float(net_income) / float(equity)) > 1.5:
            issues.append("extreme_roe")
    if pd.notna(total_assets) and pd.notna(net_income) and float(total_assets) != 0:
        if abs(float(net_income) / float(total_assets)) > 0.8:
            issues.append("extreme_roa")
    return ";".join(issues)


def enrich(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    enriched["core_metrics_present"] = enriched[CORE_FIELDS].notna().sum(axis=1)
    enriched["all_metrics_present"] = enriched[ALL_FIELDS].notna().sum(axis=1)
    enriched["missing_core_metrics"] = len(CORE_FIELDS) - enriched["core_metrics_present"]
    enriched["missing_all_metrics"] = len(ALL_FIELDS) - enriched["all_metrics_present"]
    enriched["balance_sheet_gap_pct"] = _balance_sheet_gap_pct(enriched)
    enriched["suspicious_flags"] = enriched.apply(_suspicious_flags, axis=1)
    enriched["has_all_core_metrics"] = enriched["core_metrics_present"] == len(CORE_FIELDS)
    enriched["has_all_metrics"] = enriched["all_metrics_present"] == len(ALL_FIELDS)
    return enriched


def classify_publication_status(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = enrich(frame)
    gold_mask = (
        enriched["status"].eq("ok")
        & enriched["truth_status"].eq("verified_like")
        & (enriched["core_metrics_present"] >= 7)
        & enriched["suspicious_flags"].eq("")
        & (
            enriched["balance_sheet_gap_pct"].isna()
            | (enriched["balance_sheet_gap_pct"] <= 0.10)
        )
    )

    review_mask = (
        enriched["status"].eq("ok")
        & (~gold_mask)
        & (
            (enriched["truth_status"].eq("verified_like") & (enriched["core_metrics_present"] >= 5))
            | (
                enriched["truth_status"].eq("needs_review")
                & (enriched["core_metrics_present"] >= 7)
                & enriched["suspicious_flags"].eq("")
            )
        )
    )

    enriched["publication_status"] = "exclude"
    enriched.loc[review_mask, "publication_status"] = "review"
    enriched.loc[gold_mask, "publication_status"] = "gold"
    return enriched


def _emitter_complete_count(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    return int((frame.groupby("emetteur")["fiscal_year"].nunique() == len(TARGET_YEARS)).sum())


def _write_report(audited: pd.DataFrame, classified: pd.DataFrame, gold: pd.DataFrame, review: pd.DataFrame) -> None:
    rows_expected = int(audited["emetteur"].nunique() * len(TARGET_YEARS))
    lines = [
        "# Financials Publication Report",
        "",
        "This report is the publication truth source for packaged BRVM financial-report coverage.",
        "",
        "## Publication policy",
        "",
        "- `gold`: `status=ok`, `truth_status=verified_like`, at least 7/8 core fields, no suspicious profitability/accounting flags, balance-sheet gap <= 10% when checkable.",
        "- `review`: parsed rows worth manual truth-checking before public claims.",
        "- `exclude`: missing/error rows or rows too weak for publication.",
        "",
        "## Coverage snapshot",
        "",
        f"- Rows expected in 2020-2025 window: {rows_expected}",
        f"- Audited tracking rows: {len(audited)}",
        f"- Gold rows: {len(gold)}",
        f"- Review candidates: {len(review)}",
        f"- Gold coverage ratio: {len(gold) / rows_expected:.2%}" if rows_expected else "- Gold coverage ratio: n/a",
        f"- Audited emitters: {audited['emetteur'].nunique()}",
        f"- Gold emitters: {gold['emetteur'].nunique()}",
        f"- Emitters complete on all 2020-2025 years in gold: {_emitter_complete_count(gold)}",
        f"- Emitters complete on all 2020-2025 years in review+gold: {_emitter_complete_count(classified[classified['publication_status'].isin(['gold', 'review'])])}",
        "",
        "## Gold rows by fiscal year",
        "",
    ]

    if gold.empty:
        lines.append("No gold rows available.")
    else:
        lines.extend(
            f"- {int(year)}: {int(count)}"
            for year, count in gold.groupby("fiscal_year").size().sort_index().items()
        )

    incomplete_gold = []
    for emetteur, group in gold.groupby("emetteur"):
        years = sorted(int(year) for year in group["fiscal_year"].dropna().unique())
        missing = [year for year in TARGET_YEARS if year not in years]
        if missing:
            incomplete_gold.append(f"- {emetteur}: missing {', '.join(str(year) for year in missing)}")

    lines.extend(
        [
            "",
            "## Emitters with incomplete gold coverage",
            "",
        ]
    )
    if incomplete_gold:
        lines.extend(incomplete_gold[:50])
    else:
        lines.append("None.")

    top_review = review[
        ["emetteur", "fiscal_year", "truth_status", "core_metrics_present", "suspicious_flags", "status_reason"]
    ].head(30)
    lines.extend(
        [
            "",
            "## Top review candidates",
            "",
        ]
    )
    if top_review.empty:
        lines.append("None.")
    else:
        lines.append("```text")
        lines.append(top_review.to_string(index=False))
        lines.append("```")

    REPORT_PATH.write_text("\n".join(lines) + "\n")


def build() -> None:
    source_path = RECONCILED_AUDITED_PATH if RECONCILED_AUDITED_PATH.exists() else AUDITED_PATH
    audited = _load(source_path)
    classified = classify_publication_status(audited)
    gold = classified[classified["publication_status"] == "gold"].copy()
    review = classified[classified["publication_status"] == "review"].copy()

    ordered_columns = [
        "publication_status",
        "core_metrics_present",
        "missing_core_metrics",
        "all_metrics_present",
        "missing_all_metrics",
        "has_all_core_metrics",
        "has_all_metrics",
        "balance_sheet_gap_pct",
        "suspicious_flags",
    ]
    front_columns = [column for column in ordered_columns if column in gold.columns]

    gold = gold[front_columns + [column for column in gold.columns if column not in front_columns]]
    review = review[front_columns + [column for column in review.columns if column not in front_columns]]

    gold.to_csv(GOLD_PATH, index=False)
    review.to_csv(REVIEW_PATH, index=False)
    _write_report(audited, classified, gold, review)

    RESOURCES_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(GOLD_PATH, PACKAGED_GOLD_PATH)
    shutil.copy2(REPORT_PATH, PACKAGED_REPORT_PATH)

    print(f"Using source {source_path}")
    print(f"Wrote {GOLD_PATH}")
    print(f"Wrote {REVIEW_PATH}")
    print(f"Wrote {REPORT_PATH}")
    print(f"Packaged {PACKAGED_GOLD_PATH}")
    print(f"Packaged {PACKAGED_REPORT_PATH}")


if __name__ == "__main__":
    build()
