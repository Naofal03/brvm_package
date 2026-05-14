#!/usr/bin/env python3
"""Ingest BRVM financial data from CSV into SQLite database."""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import pandas as pd

# Mapping: CSV emitter name → BRVM ticker symbol (None = not an equity / not in catalog)
EMITTER_TO_SYMBOL: dict[str, str | None] = {
    "AIR LIQUIDE CI": None,               # delisted / not in current equity catalog
    "BANK OF AFRICA BF": "BOABF",
    "BANK OF AFRICA BN": "BOAB",          # BOA Bénin
    "BANK OF AFRICA CI": "BOAC",
    "BANK OF AFRICA ML": "BOAM",
    "BANK OF AFRICA NG": "BOAN",
    "BANK OF AFRICA SN": "BOAS",
    "BBGCI": None,                         # not in equity catalog
    "BERNABE CI": "BNBC",
    "BICI CI": "BICC",
    "BIIC": "BICB",                        # BICI Bénin
    "BOLLORE TRANSPORT & LOGISTICS": "SDSC",
    "BOLLORE TRANSPORT LOGISTICS": "SDSC", # alternate spelling in CSV
    "CFAO MOTORS CI": "CFAC",
    "CIE CI": "CIEC",
    "CORIS BANK INTERNATIONAL": "CBIBF",
    "COTE D'IVOIRE TELECOM": None,         # delisted
    "CROWN SIEM CI": "SEMC",
    "DC/BR": None,                         # bond instrument
    "ECOBANK CI": "ECOC",
    "ECOBANK TG": "ETIT",
    "EDKSN": None,                         # bond / special instrument
    "FCTC SONATEL": None,                  # FCT bond
    "FCTCEPT": None,                       # FCT bond
    "FCTCSNTS": None,                      # FCT bond
    "FIDELIS FINANCE": None,               # not in equity catalog
    "FILTISAC CI": "FTSC",
    "FIMSN.O1": None,                      # bond instrument
    "FOCUS IMMOBILIER SA": None,           # not in equity catalog
    "LNB": "LNBB",
    "MOVIS CI": None,                      # not in equity catalog
    "NEI-CEDA CI": "NEIC",
    "NESTLE CI": "NTLC",
    "NOURMONY HOLDING": None,              # not in equity catalog
    "NSBC": "NSBC",
    "ONATEL BF": "ONTBF",
    "ORAGROUP": "ORGT",
    "ORANGE CI": "ORAC",
    "PALM CI": "PALC",
    "SAFCA CI": "SAFC",
    "SANCFIS FASO SA": None,               # not in equity catalog
    "SAPH CI": "SPHC",
    "SDMA S.A": None,                      # not in equity catalog
    "SERVAIR ABIDJAN CI": "ABJC",
    "SETAO CI": "STAC",
    "SGCI": "SGBC",
    "SIB": "SIBC",
    "SICABLE": "CABC",
    "SICOR": "SICC",
    "SIMPA SA": None,                      # not in equity catalog
    "SITAB": "STBC",
    "SMB": "SMBC",
    "SODECI": "SDCC",
    "SOGB": "SOGC",
    "SOLIBRA": "SLBC",
    "SONATEL": "SNTS",
    "SUCRIVOIRE": "SCRC",
    "SOCIÉTÉ IVOIRIENNE DE RAFFINAGE": None,
    "TEYLIMOGPCI": None,                   # not in equity catalog
    "TNC_FIDFIN.O1": None,                 # TNC bond
    "TNC_NMHGCINC.O1": None,              # TNC bond
    "TNC_SCFBF.O1": None,                 # TNC bond
    "TNC_SDMACI.O1": None,                # TNC bond
    "TNC_SIMPSNNC.O1": None,             # TNC bond
    "TOTAL": "TTLC",                       # TotalEnergies Côte d'Ivoire
    "TOTAL SENEGAL S.A.": "TTLS",         # TotalEnergies Sénégal
    "TPBF": None,                          # Titres Publics Burkina Faso (bonds)
    "TPBJ": None,                          # Titres Publics Bénin/Bénin (bonds)
    "TPCI": None,                          # Titres Publics Côte d'Ivoire (bonds)
    "TRACTAFRIC CI": "PRSC",
    "TRITRAF CI": None,                    # not in equity catalog
    "UNILEVER CI": "UNLC",
    "UNIWAX CI": "UNXC",
    "VIVO ENERGY CI": "SHEC",
}

TARGET_YEARS = set(range(2020, 2026))
CSV_CANDIDATES = [
    Path("data/brvm_financials_2020_2025.csv"),
    Path("data/brvm_financials_all.csv"),
]
DB_PATH = Path("data/brvm.sqlite3")

# Physically-impossible thresholds for auto-cleaning (values in raw FCFA)
# Any value outside these bounds for a BRVM listed company is an OCR error.
# Smallest listed BRVM company has ~1 billion FCFA total assets;
# largest (Sonatel + banks) is under 3 trillion.
MAX_PLAUSIBLE_VALUE = 5e13   # 50 trillion FCFA – absolute ceiling
MIN_PLAUSIBLE_ASSET = 1e8    # 100 million FCFA – minimum meaningful asset base


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


def _is_plausible(value: float | None) -> bool:
    """Return False if value is NaN, infinite, or physically impossible for a BRVM company."""
    if value is None:
        return True  # None is fine (missing data, not wrong data)
    if math.isnan(value) or math.isinf(value):
        return False
    if abs(value) > MAX_PLAUSIBLE_VALUE:
        return False
    return True


def _clean_row(row: dict) -> dict:
    """Null-out any monetary field that is physically implausible (OCR error)."""
    monetary_fields = (
        "chiffre_affaires", "resultat_operationnel", "resultat_net",
        "capitaux_propres", "total_actif", "dettes_totales",
        "actifs_courants", "passifs_courants",
    )
    cleaned = dict(row)
    for field in monetary_fields:
        raw = cleaned.get(field)
        if raw is not None:
            try:
                fval = float(raw)
            except (TypeError, ValueError):
                cleaned[field] = None
                continue
            if not _is_plausible(fval):
                print(f"  [ANOMALIE] {field}={fval:.3e} pour {cleaned.get('emetteur')} {cleaned.get('fiscal_year')} -> mis a NULL")
                cleaned[field] = None
    return cleaned


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
            continue

        row_dict = _clean_row(row.to_dict())

        snapshot_date = f"{int(row['fiscal_year'])}-12-31"

        c.execute(
            "SELECT id FROM fundamental_snapshots WHERE symbol = ? AND snapshot_date = ?",
            (symbol, snapshot_date),
        )
        existing = c.fetchone()

        revenue = row_dict.get("chiffre_affaires")
        operating_income = row_dict.get("resultat_operationnel")
        net_income = row_dict.get("resultat_net")
        equity = row_dict.get("capitaux_propres")
        total_assets = row_dict.get("total_actif")
        total_liabilities = row_dict.get("dettes_totales")
        current_assets = row_dict.get("actifs_courants")
        current_liabilities = row_dict.get("passifs_courants")
        operating_margin = row_dict.get("marge_operationnelle")
        net_margin = row_dict.get("marge_nette")
        roe = row_dict.get("roe")
        roa = row_dict.get("roa")
        debt_ratio = row_dict.get("ratio_endettement")
        equity_ratio = row_dict.get("autonomie_financiere")
        current_ratio = row_dict.get("ratio_liquidite_generale")

        # Recompute ratios if raw fields were cleaned to None
        def _ratio(num, den):
            if num is None or den is None or den == 0:
                return None
            return num / den

        if operating_margin is None:
            operating_margin = _ratio(operating_income, revenue)
        if net_margin is None:
            net_margin = _ratio(net_income, revenue)
        if roe is None:
            roe = _ratio(net_income, equity)
        if roa is None:
            roa = _ratio(net_income, total_assets)
        if debt_ratio is None:
            debt_ratio = _ratio(total_liabilities, equity)
        if equity_ratio is None:
            equity_ratio = _ratio(equity, total_assets)
        if current_ratio is None:
            current_ratio = _ratio(current_assets, current_liabilities)

        if existing:
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
        ca_str = f"{revenue:.2e}" if revenue is not None else "N/A"
        ni_str = f"{net_income:.2e}" if net_income is not None else "N/A"
        ta_str = f"{total_assets:.2e}" if total_assets is not None else "N/A"
        print(f"  [OK] {symbol:8s} ({row['emetteur']}) FY{int(row['fiscal_year'])}: CA={ca_str}, NI={ni_str}, TA={ta_str}")

    conn.commit()

    print(f"\n=== Resume ({csv_path}) ===")
    print(f"Inseres/Mis a jour : {updated}")
    print(f"Ignores (obligations/hors catalogue) : {skipped}")

    c.execute(
        "SELECT COUNT(*), COUNT(roe), COUNT(roa), COUNT(equity), COUNT(total_assets) "
        "FROM fundamental_snapshots"
    )
    total, with_roe, with_roa, with_equity, with_ta = c.fetchone()
    print(f"\nTotal snapshots en DB : {total}")
    print(f"Avec ROE             : {with_roe}")
    print(f"Avec ROA             : {with_roa}")
    print(f"Avec Capitaux propres: {with_equity}")
    print(f"Avec Total actif     : {with_ta}")

    c.execute(
        "SELECT symbol, COUNT(*) as n FROM fundamental_snapshots "
        "GROUP BY symbol ORDER BY n DESC LIMIT 30"
    )
    print("\nTop symboles en DB:")
    for sym, cnt in c.fetchall():
        print(f"  {sym}: {cnt} années")

    conn.close()


if __name__ == "__main__":
    ingest()
