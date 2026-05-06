#!/usr/bin/env python3
"""Audit BRVM financial export and classify rows by confidence."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

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


def classify_row(row: pd.Series) -> tuple[str, str]:
    status = row.get("status")
    if status in {"missing_report", "report_error", "parsed_but_empty", "company_error"}:
        return ("missing_or_error", status or "unknown")

    issues: list[str] = []
    core_count = sum(pd.notna(row.get(field)) for field in CORE_FIELDS)
    equity = row.get("capitaux_propres")
    total_assets = row.get("total_actif")
    total_debts = row.get("dettes_totales")
    revenue = row.get("chiffre_affaires")
    net_income = row.get("resultat_net")

    if core_count < 5:
        issues.append(f"core_metrics<{core_count}")
    if pd.notna(equity) and float(equity) <= 0:
        issues.append("non_positive_equity")
    if pd.notna(total_assets) and float(total_assets) <= 0:
        issues.append("non_positive_total_assets")
    if pd.notna(total_debts) and float(total_debts) < 0:
        issues.append("negative_total_debts")
    if pd.notna(total_assets) and pd.notna(equity) and float(total_assets) < float(equity):
        issues.append("assets_lt_equity")
    if pd.notna(total_assets) and pd.notna(total_debts) and pd.notna(equity):
        gap = abs(float(total_assets) - (float(total_debts) + float(equity)))
        if gap > max(abs(float(total_assets)), 1.0) * 0.1:
            issues.append("balance_sheet_gap_gt_10pct")
    if pd.notna(revenue) and pd.notna(equity) and float(revenue) == float(equity):
        issues.append("revenue_equals_equity")
    if pd.notna(revenue) and float(revenue) == 0:
        issues.append("zero_revenue")
    if pd.notna(net_income) and pd.notna(revenue) and float(revenue) != 0:
        margin = float(net_income) / float(revenue)
        if abs(margin) > 1.5:
            issues.append("extreme_net_margin")

    if issues:
        return ("needs_review", ";".join(issues))
    return ("verified_like", "passes_rule_checks")


def main() -> None:
    csv_path = resolve_csv_path()
    dataframe = pd.read_csv(csv_path)
    audits = dataframe.apply(classify_row, axis=1, result_type="expand")
    dataframe["truth_status"] = audits[0]
    dataframe["truth_reason"] = audits[1]

    print(f"Source: {csv_path}")
    print("\nTruth status summary:")
    print(dataframe["truth_status"].value_counts(dropna=False).to_string())

    print("\nRows needing review:")
    flagged = dataframe[dataframe["truth_status"] != "verified_like"][
        [
            "emetteur",
            "fiscal_year",
            "status",
            "status_reason",
            "core_metrics_count",
            "truth_status",
            "truth_reason",
        ]
    ]
    if flagged.empty:
        print("None")
    else:
        print(flagged.to_string(index=False))

    output_path = csv_path.with_name(csv_path.stem + "_audited.csv")
    dataframe.to_csv(output_path, index=False)
    print(f"\nWrote audited export to {output_path}")

    verified_only_path = csv_path.with_name(csv_path.stem + "_verified.csv")
    dataframe[dataframe["truth_status"] == "verified_like"].to_csv(verified_only_path, index=False)
    print(f"Wrote verified-only export to {verified_only_path}")


if __name__ == "__main__":
    main()
