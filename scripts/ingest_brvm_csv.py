#!/usr/bin/env python3
"""Ingest BRVM financial data from CSV into SQLite database."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

# Mapping: CSV emitter name → BRVM ticker symbol
EMITTER_TO_SYMBOL = {
    "AIR LIQUIDE CI": None,  # Not in current catalog
    "BANK OF AFRICA BF": "BOABF",
    "BANK OF AFRICA BN": None,  # Not in current catalog
    "BANK OF AFRICA CI": "BOAC",
    "BANK OF AFRICA ML": "BOAM",
    "BANK OF AFRICA SN": "BOAS",
    "BERNABE CI": "BNBC",
    "BICI CI": "BICC",
    "BOLLORE TRANSPORT LOGISTICS": "SDSC",
    "CIE CI": "CIEC",
    "CROWN SIEM CI": "SEMC",
    "FILTISAC CI": "FTSC",
    "MOVIS CI": None,  # Not in current catalog
    "NESTLE CI": "NTLC",
    "NSBC": "NSBC",
    "PALM CI": "PALC",
    "SAFCA CI": "SAFC",
    "SAPH CI": "SPHC",
    "SERVAIR ABIDJAN CI": "ABJC",
    "SETAO CI": "STAC",
    "SGCI": "SGBC",
}

TARGET_YEARS = set(range(2020, 2026))
CSV_CANDIDATES = [
    Path("data/brvm_financials_2020_2025.csv"),
    Path("data/brvm_financials_all.csv"),
]
DB_PATH = Path("data/brvm.sqlite3")


def _resolve_csv_path() -> Path:
    for path in CSV_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Aucun export financier trouvé. Fichiers attendus: "
        + ", ".join(str(path) for path in CSV_CANDIDATES)
    )


def _normalize_fiscal_year(dataframe: pd.DataFrame) -> pd.DataFrame:
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


def ingest() -> None:
    csv_path = _resolve_csv_path()
    df = _normalize_fiscal_year(pd.read_csv(csv_path))
    df = df[df["status"] == "ok"].copy()
    df = df[df["fiscal_year"].isin(TARGET_YEARS)].copy()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    updated = 0
    skipped = 0
    for _, row in df.iterrows():
        symbol = EMITTER_TO_SYMBOL.get(row["emetteur"])
        if symbol is None:
            skipped += 1
            print(f"  ⚠️ Skipping {row['emetteur']} (not in catalog)")
            continue

        snapshot_date = f"{int(row['fiscal_year'])}-12-31"

        # Check if snapshot exists
        c.execute(
            "SELECT id FROM fundamental_snapshots WHERE symbol = ? AND snapshot_date = ?",
            (symbol, snapshot_date),
        )
        existing = c.fetchone()

        # Prepare values
        revenue = row.get("chiffre_affaires")
        operating_income = row.get("resultat_operationnel")
        net_income = row.get("resultat_net")
        equity = row.get("capitaux_propres")
        total_assets = row.get("total_actif")
        total_liabilities = row.get("dettes_totales")
        current_assets = row.get("actifs_courants")
        current_liabilities = row.get("passifs_courants")
        operating_margin = row.get("marge_operationnelle")
        net_margin = row.get("marge_nette")
        roe = row.get("roe")
        roa = row.get("roa")
        debt_ratio = row.get("ratio_endettement")
        equity_ratio = row.get("autonomie_financiere")
        current_ratio = row.get("ratio_liquidite_generale")

        if existing:
            # Update existing snapshot
            c.execute(
                """
                UPDATE fundamental_snapshots SET
                    revenue = COALESCE(?, revenue),
                    operating_income = COALESCE(?, operating_income),
                    net_income = COALESCE(?, net_income),
                    equity = COALESCE(?, equity),
                    total_assets = COALESCE(?, total_assets),
                    total_liabilities = COALESCE(?, total_liabilities),
                    current_assets = COALESCE(?, current_assets),
                    current_liabilities = COALESCE(?, current_liabilities),
                    operating_margin = COALESCE(?, operating_margin),
                    net_margin = COALESCE(?, net_margin),
                    roe = COALESCE(?, roe),
                    roa = COALESCE(?, roa),
                    debt_ratio = COALESCE(?, debt_ratio),
                    equity_ratio = COALESCE(?, equity_ratio),
                    current_ratio = COALESCE(?, current_ratio),
                    source = COALESCE(source, 'brvm_pdf')
                WHERE symbol = ? AND snapshot_date = ?
                """,
                (
                    revenue, operating_income, net_income, equity, total_assets,
                    total_liabilities, current_assets, current_liabilities,
                    operating_margin, net_margin, roe, roa, debt_ratio,
                    equity_ratio, current_ratio, symbol, snapshot_date,
                ),
            )
        else:
            # Insert new snapshot
            c.execute(
                """
                INSERT INTO fundamental_snapshots (
                    symbol, snapshot_date, revenue, operating_income, net_income,
                    equity, total_assets, total_liabilities, current_assets,
                    current_liabilities, operating_margin, net_margin, roe, roa,
                    debt_ratio, equity_ratio, current_ratio, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'brvm_pdf')
                """,
                (
                    symbol, snapshot_date, revenue, operating_income, net_income,
                    equity, total_assets, total_liabilities, current_assets,
                    current_liabilities, operating_margin, net_margin, roe, roa,
                    debt_ratio, equity_ratio, current_ratio,
                ),
            )

        updated += 1
        print(f"  ✅ {symbol} ({row['emetteur']}) FY{row['fiscal_year']}: ROE={roe}, ROA={roa}")

    conn.commit()

    # Summary
    print(f"\n=== Summary ({csv_path}) ===")
    print(f"Updated/Inserted: {updated}")
    print(f"Skipped (not in catalog): {skipped}")

    c.execute(
        """
        SELECT COUNT(*), COUNT(roe), COUNT(roa), COUNT(equity), COUNT(total_assets)
        FROM fundamental_snapshots
        """
    )
    total, with_roe, with_roa, with_equity, with_ta = c.fetchone()
    print(f"\nTotal snapshots: {total}")
    print(f"With ROE: {with_roe}")
    print(f"With ROA: {with_roa}")
    print(f"With Equity: {with_equity}")
    print(f"With Total Assets: {with_ta}")

    conn.close()


if __name__ == "__main__":
    ingest()
