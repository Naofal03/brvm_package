from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import brvm as bv
import pandas as pd
from brvm_package.financial_reports.api import list_available_years
from brvm_package.api.financials_all import _apply_quality_filters, _normalize_financial_columns
from brvm_package.financial_reports.parser import FinancialReportParser
from scripts.extract_brvm_financials import (
    ReportLink,
    classify_missing_year_reason,
    count_core_metrics,
    infer_fiscal_year,
    infer_publication_year,
    resolve_report_year,
)


def test_infer_fiscal_year_prefers_exercise_year_over_publish_year() -> None:
    year = infer_fiscal_year(
        "BOA BURKINA FASO : États financiers exercice 2021",
        "https://www.brvm.org/sites/default/files/20220314_-_etats_financiers_exercice_2021_-_boa_bf.pdf",
    )
    assert year == 2021


def test_infer_publication_year_reads_url_prefix_date() -> None:
    year = infer_publication_year(
        "https://www.brvm.org/sites/default/files/20220314_-_etats_financiers_exercice_2021_-_boa_bf.pdf"
    )
    assert year == 2022


def test_financials_all_reads_local_export() -> None:
    frame = bv.financials_all()
    assert not frame.empty
    assert {"emetteur", "fiscal_year", "report_year", "status"}.issubset(frame.columns)
    assert frame["fiscal_year"].between(2020, 2025).all()
    if "truth_status" in frame.columns:
        assert (frame["truth_status"] == "verified_like").all()


def test_financials_all_audited_exposes_truth_columns() -> None:
    frame = bv.financials_all_audited()
    assert not frame.empty
    assert {"truth_status", "truth_reason"}.issubset(frame.columns)


def test_financials_all_all_mode_keeps_non_verified_rows() -> None:
    frame = bv.financials_all(mode="all")
    assert not frame.empty
    assert {"status"}.issubset(frame.columns)


def test_normalize_financial_columns_recovers_fiscal_year_from_report_title() -> None:
    frame = pd.DataFrame(
        [
            {
                "emetteur": "AIR LIQUIDE CI",
                "report_year": 2020,
                "report_title": "AIR LIQUIDE CI : Etats financiers exercice 2019",
                "report_url": "https://www.brvm.org/sites/default/files/20200915_-_etats_financiers_exercice_2019_-_air_liquide_ci.pdf",
                "status": "ok",
            }
        ]
    )
    normalized = _normalize_financial_columns(frame)
    assert normalized.empty


def test_apply_quality_filters_prefers_verified_like_rows() -> None:
    frame = pd.DataFrame(
        [
            {"emetteur": "A", "fiscal_year": 2022, "truth_status": "verified_like", "status": "ok"},
            {"emetteur": "B", "fiscal_year": 2022, "truth_status": "needs_review", "status": "ok"},
            {"emetteur": "C", "fiscal_year": 2022, "truth_status": "missing_or_error", "status": "missing_report"},
        ]
    )
    filtered = _apply_quality_filters(frame)
    assert filtered["emetteur"].tolist() == ["A"]


def test_apply_quality_filters_drops_astronomic_ocr_outliers() -> None:
    frame = pd.DataFrame(
        [
            {
                "emetteur": "BANK OF AFRICA BN",
                "fiscal_year": 2021,
                "truth_status": "verified_like",
                "status": "ok",
                "capitaux_propres": 8.983697e10,
                "total_actif": 9.027921345448844e23,
                "dettes_totales": 9.027921345447946e23,
            },
            {
                "emetteur": "BANK OF AFRICA BN",
                "fiscal_year": 2022,
                "truth_status": "verified_like",
                "status": "ok",
                "capitaux_propres": 9.719215e10,
                "total_actif": 8.844261e11,
                "dettes_totales": 7.872339e11,
            },
        ]
    )
    filtered = _apply_quality_filters(frame)
    assert filtered[["emetteur", "fiscal_year"]].to_dict("records") == [
        {"emetteur": "BANK OF AFRICA BN", "fiscal_year": 2022}
    ]


def test_count_core_metrics_counts_only_core_fields() -> None:
    metrics = {
        "resultat_operationnel": 1.0,
        "resultat_net": 2.0,
        "chiffre_affaires": None,
        "capitaux_propres": 3.0,
        "total_actif": None,
        "dettes_totales": None,
        "actifs_courants": 4.0,
        "passifs_courants": None,
        "roe": 0.1,
        "marge_nette": 0.2,
    }
    assert count_core_metrics(metrics) == 4


def test_classify_missing_year_reason_detects_nearest_report_mismatch() -> None:
    reports = [
        ReportLink(
            company_name="AIR LIQUIDE CI",
            company_url="https://www.brvm.org/fr/rapports-societe-cotes/air-liquide-ci",
            title="AIR LIQUIDE CI : Etats financiers exercice 2019",
            url="https://www.brvm.org/sites/default/files/20200915_-_etats_financiers_exercice_2019_-_air_liquide_ci.pdf",
            year=2019,
            score=120,
            publication_year=2020,
        )
    ]
    reason, diagnostic = classify_missing_year_reason(reports, 2020)
    assert reason == "nearest_report_is_different_fiscal_year"
    assert "fy=2019" in diagnostic


def test_resolve_report_year_rejects_out_of_scope_fiscal_year() -> None:
    report = ReportLink(
        company_name="AIR LIQUIDE CI",
        company_url="https://www.brvm.org/fr/rapports-societe-cotes/air-liquide-ci",
        title="AIR LIQUIDE CI : Etats financiers exercice 2019",
        url="https://www.brvm.org/sites/default/files/20200915_-_etats_financiers_exercice_2019_-_air_liquide_ci.pdf",
        year=2019,
        score=100,
    )
    assert resolve_report_year(report, [], {2020, 2021, 2022, 2023, 2024, 2025}) is None


def test_list_available_years_reads_seed_database() -> None:
    years = list_available_years("ABJC")
    assert years
    assert all(isinstance(year, int) for year in years)


def test_get_financials_supports_conservative_as_of_resolution() -> None:
    data = bv.get_financials("ABJC", as_of_date="2026-04-28")
    assert data is not None
    assert data["fiscal_year"] <= 2025
    assert data["selection_policy"] == "latest_completed_fiscal_year"


def test_collect_pipeline_module_imports() -> None:
    import brvm_package.financial_reports.collect_pipeline as collect_pipeline

    assert callable(collect_pipeline.collect_all)


def test_financial_report_parser_accepts_dataframe_items() -> None:
    parser = FinancialReportParser()
    frame = pd.DataFrame(
        [
            ["Chiffre d'affaires", "1 000"],
            ["Résultat net", "120"],
            ["Capitaux propres", "400"],
            ["Total actif", "900"],
            ["Dettes totales", "500"],
            ["Actifs courants", "300"],
            ["Passifs courants", "150"],
        ]
    )

    parsed = parser.parse([frame])

    assert parsed["revenue"] == 1000.0
    assert parsed["net_income"] == 120.0
    assert parsed["equity"] == 400.0
    assert parsed["total_assets"] == 900.0
    assert parsed["total_liabilities"] == 500.0
    assert parsed["current_assets"] == 300.0
    assert parsed["current_liabilities"] == 150.0
    assert parsed["roe"] == 0.3
