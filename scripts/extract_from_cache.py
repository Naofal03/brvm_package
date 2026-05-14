#!/usr/bin/env python3
"""
Extract financial metrics from existing OCR cache (no network needed).
Reads data/brvm_financials_cache/ocr/*.json and produces brvm_financials_all.csv
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

OCR_DIR = Path("data/brvm_financials_cache/ocr")
OUTPUT_DIR = Path("data")


@dataclass(slots=True)
class OCRToken:
    page: int
    text: str
    x: float
    y: float
    width: float
    height: float
    confidence: float


def normalize_text(value: str) -> str:
    value = value.replace("\u2019", "'").replace("\xa0", " ")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.lower()
    value = re.sub(r"[^a-z0-9%'/ -]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def extract_years(text: str) -> list[int]:
    return [int(year) for year in re.findall(r"\b(20\d{2})\b", text)]


def infer_fiscal_year(text: str) -> int | None:
    normalized = normalize_text(text.replace("_", " ").replace("-", " "))
    prioritized_patterns = [
        r"exercice\s+(20\d{2})",
        r"au\s+31\s+decembre\s+(20\d{2})",
        r"etats?\s+financiers?.*?(20\d{2})",
        r"comptes?.*?(20\d{2})",
    ]
    for pattern in prioritized_patterns:
        match = re.search(pattern, normalized)
        if match:
            return int(match.group(1))

    years = extract_years(normalized)
    if not years:
        return None
    return max(years)


def parse_amount(text: str) -> float | None:
    text = text.strip()
    if not text:
        return None
    text = (
        text.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("|", "")
        .replace("O", "0")
        .replace("o", "0")
    )
    matches = re.findall(r"-?\d[\d\s.,]*", text)
    if not matches:
        return None
    candidate = max(matches, key=lambda item: sum(ch.isdigit() for ch in item))
    candidate = candidate.replace(" ", "").replace(",", ".")
    candidate = re.sub(r"[^0-9.\-]", "", candidate)
    if candidate in {"", "-", ".", "-."}:
        return None
    try:
        return float(candidate)
    except ValueError:
        return None


def parse_amount_candidates(text: str) -> list[float]:
    stripped = text.strip()
    if not stripped:
        return []

    parts = stripped.replace("\xa0", " ").split()
    if (
        len(parts) >= 6
        and len(parts) % 2 == 0
        and all(re.fullmatch(r"-?\d{1,3}", part) if index == 0 else re.fullmatch(r"\d{3}", part) for index, part in enumerate(parts))
    ):
        midpoint = len(parts) // 2
        values: list[float] = []
        for chunk in (" ".join(parts[:midpoint]), " ".join(parts[midpoint:])):
            value = parse_amount(chunk)
            if value is not None:
                values.append(value)
        if values:
            return values

    value = parse_amount(stripped)
    return [value] if value is not None else []


def safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in {None, 0}:
        return None
    return numerator / denominator


def load_tokens(ocr_payload: dict[str, Any]) -> list[OCRToken]:
    tokens: list[OCRToken] = []
    for page in ocr_payload.get("pages", []):
        for raw in page.get("tokens", []):
            if raw.get("confidence", 0.0) < 0.2:
                continue
            tokens.append(
                OCRToken(
                    page=int(page.get("page_number", 1)),
                    text=str(raw["text"]),
                    x=float(raw["x"]),
                    y=float(raw["y"]),
                    width=float(raw["width"]),
                    height=float(raw["height"]),
                    confidence=float(raw["confidence"]),
                )
            )
    return sorted(tokens, key=lambda item: (-item.y, item.x))


def year_positions(tokens: list[OCRToken], year: int) -> list[float]:
    positions = sorted(token.x for token in tokens if normalize_text(token.text) == str(year))
    clustered: list[float] = []
    for position in positions:
        if not clustered or abs(position - clustered[-1]) > 0.03:
            clustered.append(position)
    return clustered


def label_match_score(token_text: str, labels: list[str]) -> int | None:
    normalized = normalize_text(token_text)
    best_score: int | None = None
    for label in labels:
        normalized_label = normalize_text(label)
        score: int | None = None
        if normalized == normalized_label:
            score = 100
        elif normalized.startswith(normalized_label) or normalized.endswith(normalized_label):
            score = 80
        elif normalized_label in normalized:
            score = 50
        if score is None:
            continue
        if "variation" in normalized or "flux de tresorerie" in normalized or "rendement" in normalized:
            score -= 80
        if best_score is None or score > best_score:
            best_score = score
    return best_score


def row_numeric_candidates(tokens: list[OCRToken], label_token: OCRToken) -> list[OCRToken]:
    candidates: list[OCRToken] = []
    y_tolerance = max(0.0065, min(0.012, label_token.height * 0.75))
    for token in tokens:
        if token.page != label_token.page:
            continue
        if token.x <= label_token.x + 0.03:
            continue
        if abs(token.y - label_token.y) > y_tolerance:
            continue
        values = parse_amount_candidates(token.text)
        if not values:
            continue
        if len(values) == 1:
            candidates.append(token)
            continue

        slice_width = token.width / len(values) if token.width > 0 else 0.04
        for index, value in enumerate(values):
            pseudo_text = f"{value:.0f}"
            candidates.append(
                OCRToken(
                    page=token.page,
                    text=pseudo_text,
                    x=token.x + (slice_width * index),
                    y=token.y,
                    width=slice_width,
                    height=token.height,
                    confidence=token.confidence,
                )
            )
    return candidates


def pick_value_for_label(tokens: list[OCRToken], year_x_positions: list[float], labels: list[str]) -> float | None:
    matching_tokens = [
        (score, token)
        for token in tokens
        if (score := label_match_score(token.text, labels)) is not None
    ]
    for _, token in sorted(matching_tokens, key=lambda item: (-item[0], item[1].page, -item[1].y, item[1].x)):
        candidates = row_numeric_candidates(tokens, token)
        if not candidates:
            continue
        target_positions = [position for position in year_x_positions if position > token.x]
        if not target_positions:
            target_positions = year_x_positions
        if target_positions:
            target_x = min(target_positions, key=lambda position: position - token.x if position >= token.x else math.inf)
            if math.isinf(target_x):
                target_x = min(year_x_positions, key=lambda position: abs(position - token.x))
            chosen = min(candidates, key=lambda item: abs(item.x - target_x))
        else:
            chosen = min(candidates, key=lambda item: item.x)
        value = parse_amount(chosen.text)
        if value is not None:
            return value
    return None


def pick_total_assets(tokens: list[OCRToken], year_x_positions: list[float]) -> float | None:
    labelled_tokens = []
    for token in tokens:
        normalized = normalize_text(token.text)
        score = None
        if normalized in {"total actif", "total bilan", "total passif", "total passif et capitaux propres", "total du passif et des capitaux propres"}:
            score = 100
        elif (
            ("total actif" in normalized or "total bilan" in normalized or "total passif et capitaux propres" in normalized)
            and "circulant" not in normalized
        ):
            score = 70
        if score is not None:
            labelled_tokens.append((score, token))
    for _, token in sorted(labelled_tokens, key=lambda item: (-item[0], item[1].page, -item[1].y, item[1].x)):
        values = row_numeric_candidates(tokens, token)
        if not values:
            continue
        if year_x_positions:
            target_x = min((pos for pos in year_x_positions if pos > token.x), default=min(year_x_positions))
            chosen = min(values, key=lambda item: abs(item.x - target_x))
        else:
            chosen = min(values, key=lambda item: item.x)
        value = parse_amount(chosen.text)
        if value is not None:
            return value

    return None


def extract_metrics(tokens: list[OCRToken], report_year: int) -> dict[str, float | None]:
    positions = year_positions(tokens, report_year)
    revenue = pick_value_for_label(tokens, positions, ["Chiffre d'affaires", "Chiffre d affaires"])
    operating_result = pick_value_for_label(
        tokens,
        positions,
        [
            "Résultat d'exploitation",
            "Resultat d'exploitation",
            "Resultat d exploitation",
            "Résultat opérationnel",
            "Resultat operationnel",
        ],
    )
    net_income = pick_value_for_label(tokens, positions, ["Résultat net", "Resultat net", "Bénéfice net", "Benefice net"])

    capital = pick_value_for_label(tokens, positions, ["Capital"])
    reserves = pick_value_for_label(tokens, positions, ["Primes et Réserves", "Primes et reserves"])
    current_year_result = pick_value_for_label(
        tokens,
        positions,
        ["RESULTAT DE L'EXERCICE", "Résultat de l'exercice", "Resultat de l'exercice"],
    )
    other_equity = pick_value_for_label(
        tokens,
        positions,
        ["Autres Capitaux", "Autres capitaux propres", "Autres capitaux"],
    )
    equity = pick_value_for_label(tokens, positions, ["Capitaux propres", "Total capitaux propres"])
    if equity is None:
        equity = pick_value_for_label(
            tokens,
            positions,
            [
                "CAPITAUX PROPRES ET RESSOURCES ASSIMILEES",
                "CAPITAUX PROPRES ET RESSOURCES ASSIMILLEES",
                "TOTAL CAPITAUX PROPRES ET RESSOURCES ASSIMILEES",
                "Total des capitaux propres",
                "Total capitaux propres",
                "Total capitaux propres et ressources assimilees",
            ],
        )
    if equity is None:
        equity_parts = [capital, reserves, current_year_result, other_equity]
        if any(value is not None for value in equity_parts):
            equity = sum(value or 0.0 for value in equity_parts)

    total_assets = pick_total_assets(tokens, positions)

    inventories = pick_value_for_label(tokens, positions, ["Stocks"])
    receivables = pick_value_for_label(
        tokens,
        positions,
        ["Créances et emplois assimilés", "Creances et emplois assimiles", "Créances", "Creances"],
    )
    cash_assets = pick_value_for_label(tokens, positions, ["Trésorerie - ACTIF", "Trésorerie actif", "Tresorerie - actif"])
    current_assets = pick_value_for_label(
        tokens,
        positions,
        ["Actif circulant", "Actifs courants", "TOTAL ACTIF CIRCULANT", "Actif Circulant net", "TOTAL ACTIF CRCULANT"],
    )
    if current_assets is None and any(value is not None for value in (inventories, receivables, cash_assets)):
        current_assets = sum(value or 0.0 for value in (inventories, receivables, cash_assets))

    financial_debts = pick_value_for_label(
        tokens,
        positions,
        [
            "Dettes financières",
            "Dettes financieres",
            "Emprunts et dettes financières",
            "TOTAL DETTES FINANCIERES ET RESSOURCES ASSIMILEES",
            "Dettes financières et ressources assimilées",
        ],
    )
    operating_debts = pick_value_for_label(
        tokens,
        positions,
        ["Dettes d'exploitation", "Dettes d exploitation", "Passifs courants", "Passif circulant"],
    )
    cash_liabilities = pick_value_for_label(tokens, positions, ["Trésorerie - PASSIF", "Trésorerie passif", "Tresorerie - passif"])
    total_debts = pick_value_for_label(tokens, positions, ["Dettes totales", "Total dettes"])
    if total_debts is None and any(value is not None for value in (financial_debts, operating_debts, cash_liabilities)):
        total_debts = sum(value or 0.0 for value in (financial_debts, operating_debts, cash_liabilities))

    current_liabilities = pick_value_for_label(
        tokens,
        positions,
        ["Passifs courants", "Passif circulant", "Passifs circulants", "TOTAL PASSIF CIRCULANT", "Total passif circulant"],
    )
    if current_liabilities is None and any(value is not None for value in (operating_debts, cash_liabilities)):
        current_liabilities = sum(value or 0.0 for value in (operating_debts, cash_liabilities))
    if any(value is not None for value in (financial_debts, current_liabilities)):
        combined_debts = sum(value or 0.0 for value in (financial_debts, current_liabilities))
        if total_debts is None or combined_debts > total_debts:
            total_debts = combined_debts
    if total_debts is None and total_assets is not None and equity is not None:
        total_debts = total_assets - equity
    if total_assets is None and total_debts is not None and equity is not None:
        total_assets = total_debts + equity
    if total_assets is not None and total_debts is not None and equity is not None:
        reconstructed_assets = total_debts + equity
        if reconstructed_assets > total_assets:
            total_assets = reconstructed_assets

    metrics: dict[str, float | None] = {
        "resultat_operationnel": operating_result,
        "resultat_net": net_income,
        "chiffre_affaires": revenue,
        "capitaux_propres": equity,
        "total_actif": total_assets,
        "dettes_totales": total_debts,
        "actifs_courants": current_assets,
        "passifs_courants": current_liabilities,
    }
    metrics["marge_operationnelle"] = safe_divide(metrics["resultat_operationnel"], metrics["chiffre_affaires"])
    metrics["marge_nette"] = safe_divide(metrics["resultat_net"], metrics["chiffre_affaires"])
    metrics["roe"] = safe_divide(metrics["resultat_net"], metrics["capitaux_propres"])
    metrics["roa"] = safe_divide(metrics["resultat_net"], metrics["total_actif"])
    metrics["ratio_endettement"] = safe_divide(metrics["dettes_totales"], metrics["capitaux_propres"])
    metrics["autonomie_financiere"] = safe_divide(metrics["capitaux_propres"], metrics["total_actif"])
    metrics["ratio_liquidite_generale"] = safe_divide(metrics["actifs_courants"], metrics["passifs_courants"])
    return metrics


def detect_report_year(tokens: list[OCRToken]) -> int | None:
    years: list[int] = []
    for token in tokens:
        years.extend(extract_years(token.text))
    years = [year for year in years if 2000 <= year <= 2035]
    if not years:
        return None
    return max(years)


def resolve_report_year(filename: str, tokens: list[OCRToken], fallback_year: int | None) -> int | None:
    hinted_year = infer_fiscal_year(filename)
    detected_year = detect_report_year(tokens)
    if hinted_year is not None:
        return hinted_year
    if detected_year is not None:
        return detected_year
    return fallback_year


def parse_company_year_from_stem(stem: str) -> tuple[str, int | None]:
    """Extract company slug and year from a stem like 'air-liquide-ci-2019-1'."""
    parts = stem.split("-")
    year = None
    year_idx = None
    for i, part in enumerate(parts):
        if re.match(r"^20\d{2}$", part):
            year = int(part)
            year_idx = i
            break
    if year_idx is not None:
        company_slug = "-".join(parts[:year_idx])
    else:
        company_slug = stem
    return company_slug, year


def parse_company_year_from_path(path: Path) -> tuple[str, int | None]:
    stem = path.stem
    if stem.startswith("page-") and path.parent != OCR_DIR:
        return parse_company_year_from_stem(path.parent.name)
    return parse_company_year_from_stem(stem)


def discover_cached_reports() -> dict[tuple[str, int], Path]:
    report_paths: dict[tuple[str, int], Path] = {}

    for path in sorted(OCR_DIR.rglob("*.json")):
        stem = path.stem
        if stem.startswith("page-") and path.parent != OCR_DIR:
            report_key_path = path.parent
            company_slug, year = parse_company_year_from_stem(report_key_path.name)
        else:
            report_key_path = path
            company_slug, year = parse_company_year_from_stem(stem)

        if year is None:
            continue

        key = (company_slug, year)
        current = report_paths.get(key)
        if current is None:
            report_paths[key] = report_key_path
            continue

        current_size = current.stat().st_size if current.is_file() else sum(child.stat().st_size for child in current.glob("*.json"))
        candidate_size = report_key_path.stat().st_size if report_key_path.is_file() else sum(child.stat().st_size for child in report_key_path.glob("*.json"))
        if candidate_size > current_size:
            report_paths[key] = report_key_path

    return report_paths


def load_cached_payload(path: Path) -> dict[str, Any]:
    if path.is_file():
        with open(path) as handle:
            return json.load(handle)

    combined_pages: list[dict[str, Any]] = []
    sources: list[str] = []
    for page_json in sorted(path.glob("page-*.json")):
        with open(page_json) as handle:
            payload = json.load(handle)
        sources.append(str(payload.get("source", page_json)))
        for page in payload.get("pages", []):
            combined_pages.append(page)

    return {
        "source": sources[0] if sources else str(path),
        "page_count": len(combined_pages),
        "pages": combined_pages,
    }


def main() -> None:
    ocr_files = sorted(OCR_DIR.rglob("*.json"))
    print(f"Found {len(ocr_files)} OCR files in cache")

    company_year_files = discover_cached_reports()
    print(f"Unique company-year pairs: {len(company_year_files)}")

    rows: list[dict[str, Any]] = []
    for (company_slug, year), ocr_path in sorted(company_year_files.items()):
        try:
            ocr_payload = load_cached_payload(ocr_path)
            tokens = load_tokens(ocr_payload)
            detected_year = resolve_report_year(ocr_path.name, tokens, year)

            metrics = extract_metrics(tokens, detected_year)
            row = {
                "emetteur": company_slug.replace("-", " ").upper(),
                "fiscal_year": detected_year,
                "report_year": detected_year,
                "publication_date": None,
                "status": "ok",
                **metrics,
            }
            # Check if we got any actual financial data
            has_data = any(
                value is not None
                for key, value in metrics.items()
                if key not in {"marge_operationnelle", "marge_nette", "roe", "roa", "ratio_endettement", "autonomie_financiere", "ratio_liquidite_generale"}
            )
            if not has_data:
                row["status"] = "parsed_but_empty"
            rows.append(row)
        except Exception as e:
            print(f"  Error processing {ocr_path.name}: {e}")
            rows.append({
                "emetteur": company_slug.replace("-", " ").upper(),
                "fiscal_year": year,
                "report_year": year,
                "publication_date": None,
                "status": f"error: {e}",
            })

    dataframe = pd.DataFrame(rows)
    preferred_order = [
        "emetteur",
        "fiscal_year",
        "report_year",
        "publication_date",
        "status",
        "resultat_operationnel",
        "resultat_net",
        "chiffre_affaires",
        "capitaux_propres",
        "total_actif",
        "dettes_totales",
        "actifs_courants",
        "passifs_courants",
        "marge_operationnelle",
        "marge_nette",
        "roe",
        "roa",
        "ratio_endettement",
        "autonomie_financiere",
        "ratio_liquidite_generale",
    ]
    # Only include columns that exist
    available_cols = [c for c in preferred_order if c in dataframe.columns]
    dataframe = dataframe[available_cols]

    output_path = OUTPUT_DIR / "brvm_financials_all.csv"
    dataframe.to_csv(output_path, index=False)
    try:
        dataframe.to_excel(output_path.with_suffix(".xlsx"), index=False)
    except Exception:
        pass

    print(f"\nWrote {len(dataframe)} rows to {output_path}")

    # Summary
    ok_count = (dataframe["status"] == "ok").sum()
    empty_count = (dataframe["status"] == "parsed_but_empty").sum()
    print(f"  OK: {ok_count}")
    print(f"  Parsed but empty: {empty_count}")
    print(f"  Other: {len(dataframe) - ok_count - empty_count}")

    # Show sample data
    print("\n=== Sample data (first 10 OK rows) ===")
    ok_df = dataframe[dataframe["status"] == "ok"]
    if not ok_df.empty:
        print(ok_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
