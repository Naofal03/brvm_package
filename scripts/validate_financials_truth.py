#!/usr/bin/env python3
"""Validate coverage and accounting consistency of BRVM financial exports."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

TARGET_YEARS = list(range(2020, 2026))
AUDITED_PATH = Path("data/brvm_financials_2020_2025_audited.csv")
VERIFIED_PATH = Path("data/brvm_financials_2020_2025_verified.csv")
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
RATIO_SPECS = [
    ("marge_operationnelle", "resultat_operationnel", "chiffre_affaires"),
    ("marge_nette", "resultat_net", "chiffre_affaires"),
    ("roe", "resultat_net", "capitaux_propres"),
    ("roa", "resultat_net", "total_actif"),
    ("ratio_endettement", "dettes_totales", "capitaux_propres"),
    ("autonomie_financiere", "capitaux_propres", "total_actif"),
    ("ratio_liquidite_generale", "actifs_courants", "passifs_courants"),
]


def _load_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required export: {path}")
    frame = pd.read_csv(path)
    if "fiscal_year" in frame.columns:
        frame["fiscal_year"] = pd.to_numeric(frame["fiscal_year"], errors="coerce")
        frame = frame[frame["fiscal_year"].isin(TARGET_YEARS)].copy()
    return frame


def _missing_emitters(audited: pd.DataFrame, verified: pd.DataFrame) -> list[str]:
    audited_emitters = set(audited["emetteur"].dropna().unique())
    verified_emitters = set(verified["emetteur"].dropna().unique())
    return sorted(audited_emitters - verified_emitters)


def _incomplete_emitters(verified: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for emetteur, emitter_frame in verified.groupby("emetteur"):
        years = sorted(int(year) for year in emitter_frame["fiscal_year"].dropna().unique())
        missing = [year for year in TARGET_YEARS if year not in years]
        if missing:
            rows.append(
                {
                    "emetteur": emetteur,
                    "years_present": ",".join(str(year) for year in years),
                    "missing_years": ",".join(str(year) for year in missing),
                }
            )
    return pd.DataFrame(rows).sort_values("emetteur").reset_index(drop=True) if rows else pd.DataFrame()


def _ratio_mismatches(verified: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, row in verified.iterrows():
        for ratio_name, numerator_field, denominator_field in RATIO_SPECS:
            ratio_value = row.get(ratio_name)
            numerator = row.get(numerator_field)
            denominator = row.get(denominator_field)
            if pd.isna(ratio_value) or pd.isna(numerator) or pd.isna(denominator) or float(denominator) == 0.0:
                continue
            computed = float(numerator) / float(denominator)
            diff = abs(float(ratio_value) - computed)
            rel_diff = diff / max(abs(computed), 1e-12)
            if diff > 1e-6 and rel_diff > 1e-3:
                rows.append(
                    {
                        "emetteur": row["emetteur"],
                        "fiscal_year": int(row["fiscal_year"]),
                        "ratio": ratio_name,
                        "stored_value": float(ratio_value),
                        "computed_value": computed,
                        "relative_diff": rel_diff,
                    }
                )
    return pd.DataFrame(rows)


def _accounting_gaps(verified: pd.DataFrame) -> pd.DataFrame:
    checked = verified[["emetteur", "fiscal_year", "capitaux_propres", "total_actif", "dettes_totales"]].dropna().copy()
    checked["gap_pct"] = (
        (checked["total_actif"] - (checked["capitaux_propres"] + checked["dettes_totales"])).abs()
        / checked["total_actif"].abs().replace(0, pd.NA)
    )
    return checked.sort_values("gap_pct", ascending=False).reset_index(drop=True)


def _suspicious_rows(verified: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, row in verified.iterrows():
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

        if issues:
            rows.append(
                {
                    "emetteur": row["emetteur"],
                    "fiscal_year": int(row["fiscal_year"]),
                    "issues": ";".join(issues),
                }
            )
    return pd.DataFrame(rows).sort_values(["emetteur", "fiscal_year"]).reset_index(drop=True) if rows else pd.DataFrame()


def main() -> None:
    audited = _load_frame(AUDITED_PATH)
    verified = _load_frame(VERIFIED_PATH)
    verified = verified.copy()
    verified["missing_core_count"] = verified[CORE_FIELDS].isna().sum(axis=1)

    missing_emitters = _missing_emitters(audited, verified)
    incomplete_emitters = _incomplete_emitters(verified)
    ratio_mismatches = _ratio_mismatches(verified)
    accounting_gaps = _accounting_gaps(verified)
    suspicious_rows = _suspicious_rows(verified)

    print(f"Audited rows: {len(audited)}")
    print(f"Verified rows: {len(verified)}")
    print(f"Audited emitters: {audited['emetteur'].nunique()}")
    print(f"Verified emitters: {verified['emetteur'].nunique()}")
    print(f"Emitters with zero verified rows: {len(missing_emitters)}")
    print(f"Emitters with missing years inside 2020-2025: {len(incomplete_emitters)}")
    print("\nVerified rows by year:")
    print(verified.groupby("fiscal_year").size().to_string())
    print("\nMissing core metrics distribution:")
    print(verified["missing_core_count"].value_counts().sort_index().to_string())

    checked_gaps = accounting_gaps["gap_pct"].dropna()
    print("\nAccounting identity quality:")
    print(f"Rows checked: {len(accounting_gaps)}")
    print(f"Gap <= 1%: {(checked_gaps <= 0.01).sum()}")
    print(f"Gap <= 5%: {(checked_gaps <= 0.05).sum()}")
    print(f"Gap <= 10%: {(checked_gaps <= 0.10).sum()}")
    print(f"Ratio mismatches vs stored formulas: {len(ratio_mismatches)}")
    print(f"Suspicious rows to review: {len(suspicious_rows)}")

    if missing_emitters:
        print("\nEmitters with zero verified rows:")
        for emetteur in missing_emitters:
            print(f"- {emetteur}")

    if not incomplete_emitters.empty:
        print("\nEmitters with incomplete 2020-2025 coverage:")
        print(incomplete_emitters.to_string(index=False))

    if not suspicious_rows.empty:
        print("\nSuspicious verified rows:")
        print(suspicious_rows.to_string(index=False))

    if not accounting_gaps.empty:
        print("\nWorst accounting gaps:")
        print(accounting_gaps.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
