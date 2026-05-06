from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.extract_from_cache import extract_metrics, load_tokens, parse_amount_candidates
from scripts.extract_brvm_financials import extract_metrics_from_pdf_tables


def _load_tokens(relative_path: str):
    payload = json.loads((ROOT / "data" / "brvm_financials_cache" / "ocr" / relative_path).read_text())
    return load_tokens(payload)


def test_parse_amount_candidates_splits_two_joined_bank_values() -> None:
    values = parse_amount_candidates("97 192 147 880 104 674 009 283")
    assert values == [97192147880.0, 104674009283.0]


def test_servair_balance_sheet_totals_extract_from_cache() -> None:
    metrics = extract_metrics(_load_tokens("servair-abidjan-ci-2020-10/page-001.json"), 2020)
    assert metrics["capitaux_propres"] == 304746668.0
    assert metrics["dettes_totales"] == 487779317.0 + 3006255558.0
    assert metrics["passifs_courants"] == 3006255558.0
    assert metrics["total_actif"] == metrics["capitaux_propres"] + metrics["dettes_totales"]


def test_bank_of_africa_bn_equity_extracts_from_joined_cell() -> None:
    metrics = extract_metrics(_load_tokens("bank-of-africa-bn-2022-2/page-002.json"), 2022)
    assert metrics["capitaux_propres"] == 97192147880.0


def test_orange_ci_2025_table_fallback_extracts_scaled_financials() -> None:
    metrics = extract_metrics_from_pdf_tables(
        ROOT / "data" / "brvm_financials_cache" / "pdfs" / "orange-ci-2025-1.pdf",
        2025,
    )
    assert metrics["chiffre_affaires"] == 1197100000000.0
    assert metrics["resultat_operationnel"] == 287200000000.0
    assert metrics["resultat_net"] == 167800000000.0
    assert metrics["capitaux_propres"] == 707800000000.0
    assert metrics["total_actif"] == 2554100000000.0
    assert metrics["passifs_courants"] == 1520200000000.0
