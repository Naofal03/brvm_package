#!/usr/bin/env python3
"""Reconcile audited BRVM financial export with stricter cache-derived candidates."""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.extract_from_cache as cache  # noqa: E402

AUDITED_PATH = Path("data/brvm_financials_2020_2025_audited.csv")
VERIFIED_PATH = Path("data/brvm_financials_2020_2025_verified.csv")
RECONCILED_AUDITED_PATH = Path("data/brvm_financials_2020_2025_reconciled_audited.csv")
RECONCILED_VERIFIED_PATH = Path("data/brvm_financials_2020_2025_reconciled_verified.csv")
RECONCILIATION_REPORT_PATH = Path("data/financials_reconciliation_report.md")

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
RATIO_FIELDS = [
    "marge_operationnelle",
    "marge_nette",
    "roe",
    "roa",
    "ratio_endettement",
    "autonomie_financiere",
    "ratio_liquidite_generale",
]
TARGET_YEARS = set(range(2020, 2026))
MAX_REASONABLE_TOTAL_FCFA = 1e15


def normalize_emitter(value: str) -> str:
    return (
        str(value)
        .upper()
        .replace("É", "E")
        .replace("È", "E")
        .replace("Ê", "E")
        .replace("’", "'")
    )


def canonical_emitter_lookup(frame: pd.DataFrame) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for emitter in frame["emetteur"].dropna().astype(str).unique():
        key = pd.Series([emitter]).str.replace(r"[^A-Z0-9]+", " ", regex=True).str.strip().str.upper().iloc[0]
        lookup[key] = emitter
    return lookup


def balance_sheet_gap_pct(row: pd.Series) -> float | None:
    total_assets = row.get("total_actif")
    equity = row.get("capitaux_propres")
    total_debts = row.get("dettes_totales")
    if pd.isna(total_assets) or pd.isna(equity) or pd.isna(total_debts) or float(total_assets) == 0.0:
        return None
    return abs(float(total_assets) - (float(equity) + float(total_debts))) / abs(float(total_assets))


def candidate_issues(row: pd.Series) -> list[str]:
    issues: list[str] = []
    revenue = row.get("chiffre_affaires")
    operating_income = row.get("resultat_operationnel")
    net_income = row.get("resultat_net")
    equity = row.get("capitaux_propres")
    total_assets = row.get("total_actif")
    total_debts = row.get("dettes_totales")
    current_assets = row.get("actifs_courants")
    current_liabilities = row.get("passifs_courants")

    if pd.notna(equity) and float(equity) <= 0:
        issues.append("non_positive_equity")
    if pd.notna(total_assets) and float(total_assets) <= 0:
        issues.append("non_positive_total_assets")
    if pd.notna(total_debts) and float(total_debts) < 0:
        issues.append("negative_total_debts")
    if pd.notna(current_assets) and float(current_assets) < 0:
        issues.append("negative_current_assets")
    if pd.notna(current_liabilities) and float(current_liabilities) < 0:
        issues.append("negative_current_liabilities")
    if pd.notna(total_assets) and float(total_assets) > MAX_REASONABLE_TOTAL_FCFA:
        issues.append("astronomic_total_assets")
    if pd.notna(total_debts) and float(total_debts) > MAX_REASONABLE_TOTAL_FCFA:
        issues.append("astronomic_total_debts")
    if pd.notna(revenue) and pd.notna(operating_income) and float(revenue) != 0:
        if abs(float(operating_income) / float(revenue)) > 1.2:
            issues.append("extreme_operating_margin")
    if pd.notna(revenue) and pd.notna(net_income) and float(revenue) != 0:
        if abs(float(net_income) / float(revenue)) > 1.2:
            issues.append("extreme_net_margin")
    if pd.notna(revenue) and pd.notna(total_assets):
        scale_ratio = abs(float(revenue)) / max(abs(float(total_assets)), 1.0)
        if scale_ratio > 100 or scale_ratio < 0.0001:
            issues.append("revenue_total_assets_scale_mismatch")
    if pd.notna(current_assets) and pd.notna(total_assets) and float(total_assets) != 0:
        current_asset_ratio = abs(float(current_assets)) / abs(float(total_assets))
        if current_asset_ratio < 0.00001:
            issues.append("current_assets_scale_mismatch")
    if pd.notna(current_liabilities) and pd.notna(total_assets) and float(total_assets) != 0:
        current_liability_ratio = abs(float(current_liabilities)) / abs(float(total_assets))
        if current_liability_ratio < 0.00001:
            issues.append("current_liabilities_scale_mismatch")
    if pd.notna(equity) and pd.notna(net_income) and float(equity) != 0:
        if abs(float(net_income) / float(equity)) > 1.5:
            issues.append("extreme_roe")
    if pd.notna(total_assets) and pd.notna(net_income) and float(total_assets) != 0:
        if abs(float(net_income) / float(total_assets)) > 0.8:
            issues.append("extreme_roa")
    gap = balance_sheet_gap_pct(row)
    if gap is not None and gap > 0.10:
        issues.append("balance_sheet_gap_gt_10pct")
    return issues


def build_cache_candidates(audited: pd.DataFrame) -> pd.DataFrame:
    emitter_lookup = canonical_emitter_lookup(audited)
    report_map = cache.discover_cached_reports()
    rows: list[dict[str, Any]] = []

    for (company_slug, fallback_year), path in sorted(report_map.items()):
        payload = cache.load_cached_payload(path)
        tokens = cache.load_tokens(payload)
        detected_year = cache.resolve_report_year(path.name, tokens, fallback_year)
        if detected_year not in TARGET_YEARS:
            continue

        metrics = cache.extract_metrics(tokens, detected_year)
        normalized_key = pd.Series([company_slug.replace("-", " ").upper()]).str.replace(
            r"[^A-Z0-9]+", " ", regex=True
        ).str.strip().iloc[0]
        canonical_emitter = emitter_lookup.get(normalized_key, company_slug.replace("-", " ").upper())
        row = {
            "emetteur": canonical_emitter,
            "normalized_emetteur": normalized_key,
            "fiscal_year": detected_year,
            **metrics,
        }
        row["core_metrics_present"] = sum(pd.notna(row.get(field)) for field in CORE_FIELDS)
        row["candidate_issues"] = ";".join(candidate_issues(pd.Series(row)))
        scale_fields = [row.get("chiffre_affaires"), row.get("capitaux_propres"), row.get("total_actif")]
        scale_values = [float(value) for value in scale_fields if pd.notna(value)]
        row["max_scale_value"] = max(scale_values) if scale_values else None
        rows.append(row)

    return pd.DataFrame(rows)


def should_replace(audited_row: pd.Series, candidate_row: pd.Series) -> bool:
    if candidate_row.get("core_metrics_present", 0) < 5:
        return False
    if candidate_row.get("candidate_issues"):
        return False
    max_scale = candidate_row.get("max_scale_value")
    if pd.isna(max_scale) or float(max_scale) < 1e8:
        return False

    audited_truth = str(audited_row.get("truth_status", ""))
    audited_core = int(audited_row.get("core_metrics_count", 0) or 0)
    audited_gap = balance_sheet_gap_pct(audited_row)
    candidate_gap = balance_sheet_gap_pct(candidate_row)

    if audited_truth == "verified_like":
        return False
    if candidate_row["core_metrics_present"] > audited_core:
        return True
    if audited_gap is not None and audited_gap > 0.10 and (candidate_gap is None or candidate_gap <= 0.10):
        return True
    if "non_positive_equity" in str(audited_row.get("truth_reason", "")) and pd.notna(candidate_row.get("capitaux_propres")):
        return float(candidate_row["capitaux_propres"]) > 0
    return False


def apply_candidate(audited_row: pd.Series, candidate_row: pd.Series) -> pd.Series:
    updated = audited_row.copy()
    for field in CORE_FIELDS + RATIO_FIELDS:
        if field in candidate_row and pd.notna(candidate_row[field]):
            updated[field] = candidate_row[field]
    updated["core_metrics_count"] = int(candidate_row["core_metrics_present"])
    updated["truth_status"] = "verified_like"
    updated["truth_reason"] = "reconciled_from_cache_candidate"
    updated["status"] = "ok"
    updated["status_reason"] = updated.get("status_reason") or ""
    updated["diagnostic"] = "reconciled_from_cache_candidate"
    return updated


def main() -> None:
    audited = pd.read_csv(AUDITED_PATH)
    candidates = build_cache_candidates(audited)
    if candidates.empty:
        raise RuntimeError("No cache candidates available.")

    candidate_map = {
        (row["emetteur"], int(row["fiscal_year"])): row
        for _, row in candidates.sort_values(["core_metrics_present", "max_scale_value"], ascending=[False, False]).iterrows()
    }

    reconciled = audited.copy()
    replaced: list[dict[str, Any]] = []
    for index, row in reconciled.iterrows():
        key = (row["emetteur"], int(row["fiscal_year"]))
        candidate = candidate_map.get(key)
        if candidate is None:
            continue
        if not should_replace(row, candidate):
            continue
        replaced.append(
            {
                "emetteur": row["emetteur"],
                "fiscal_year": int(row["fiscal_year"]),
                "old_truth_status": row.get("truth_status"),
                "old_truth_reason": row.get("truth_reason"),
                "old_core_metrics_count": row.get("core_metrics_count"),
                "new_core_metrics_count": candidate["core_metrics_present"],
            }
        )
        reconciled.loc[index] = apply_candidate(row, candidate)

    reconciled.to_csv(RECONCILED_AUDITED_PATH, index=False)
    reconciled[reconciled["truth_status"] == "verified_like"].to_csv(RECONCILED_VERIFIED_PATH, index=False)

    report_lines = [
        "# Financials Reconciliation Report",
        "",
        f"- Replaced rows: {len(replaced)}",
        f"- Reconciled audited file: `{RECONCILED_AUDITED_PATH}`",
        f"- Reconciled verified file: `{RECONCILED_VERIFIED_PATH}`",
        "",
    ]
    if replaced:
        report_lines.append("## Replaced rows")
        report_lines.append("")
        report_lines.append(pd.DataFrame(replaced).to_string(index=False))
        report_lines.append("")

    RECONCILIATION_REPORT_PATH.write_text("\n".join(report_lines) + "\n")
    print(f"Wrote {RECONCILED_AUDITED_PATH}")
    print(f"Wrote {RECONCILED_VERIFIED_PATH}")
    print(f"Wrote {RECONCILIATION_REPORT_PATH}")
    print(f"Replaced rows: {len(replaced)}")


if __name__ == "__main__":
    main()
