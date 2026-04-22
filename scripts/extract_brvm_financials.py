from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
import pandas as pd
import pdfplumber
from bs4 import BeautifulSoup

BASE_URL = "https://www.brvm.org"
LISTING_URL = f"{BASE_URL}/fr/rapports-societes-cotees"
DEFAULT_YEARS = list(range(2020, 2026))
USER_AGENT = "Mozilla/5.0 (compatible; brvm-package/0.1; +https://github.com/naofal/brvm-package)"

ROOT = Path(__file__).resolve().parents[1]
SWIFT_SCRIPT = ROOT / "scripts" / "brvm_pdf_ocr.swift"
SPLIT_SCRIPT = ROOT / "scripts" / "split_pdf_pages.swift"
CACHE_DIR = ROOT / "data" / "brvm_financials_cache"
PDF_DIR = CACHE_DIR / "pdfs"
PNG_DIR = CACHE_DIR / "png"
OCR_DIR = CACHE_DIR / "ocr"
OUTPUT_DIR = ROOT / "data"


@dataclass(slots=True)
class CompanyLink:
    name: str
    url: str


@dataclass(slots=True)
class ReportLink:
    company_name: str
    company_url: str
    title: str
    url: str
    year: int | None
    score: int


@dataclass(slots=True)
class OCRToken:
    page: int
    text: str
    x: float
    y: float
    width: float
    height: float
    confidence: float


def slugify(value: str) -> str:
    cleaned = unicodedata.normalize("NFKD", value)
    cleaned = "".join(char for char in cleaned if not unicodedata.combining(char))
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", cleaned).strip("-").lower()
    return cleaned or "item"


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


def safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in {None, 0}:
        return None
    return numerator / denominator


def ensure_dirs() -> None:
    for path in (CACHE_DIR, PDF_DIR, PNG_DIR, OCR_DIR, OUTPUT_DIR):
        path.mkdir(parents=True, exist_ok=True)


def fetch_html(client: httpx.Client, url: str) -> str:
    response = client.get(url, headers={"User-Agent": USER_AGENT}, timeout=60.0, follow_redirects=True)
    response.raise_for_status()
    return response.text


def crawl_company_links(client: httpx.Client, max_pages: int = 12) -> list[CompanyLink]:
    discovered: dict[str, CompanyLink] = {}
    for page in range(max_pages):
        url = LISTING_URL if page == 0 else f"{LISTING_URL}?page={page}"
        soup = BeautifulSoup(fetch_html(client, url), "html.parser")
        anchors = soup.select("a[href^='/fr/rapports-societe-cotes/']")
        page_count_before = len(discovered)
        for anchor in anchors:
            href = anchor.get("href", "").strip()
            name = anchor.get_text(" ", strip=True)
            if not href or not name:
                continue
            absolute = urljoin(BASE_URL, href)
            if absolute not in discovered:
                discovered[absolute] = CompanyLink(name=name, url=absolute)
        if len(discovered) == page_count_before:
            break
    return sorted(discovered.values(), key=lambda item: item.name)


def report_score(title: str, target_year: int) -> int:
    normalized = normalize_text(title)
    score = 0
    if "etat financier" in normalized:
        score += 120
    if str(target_year) in normalized:
        score += 60
    if "approuve" in normalized or "annuel" in normalized or "systeme normal" in normalized:
        score += 35
    if "provisoire" in normalized:
        score += 10
    if "rapport des commissaires" in normalized or "rapport des cacs" in normalized or "cac" in normalized:
        score -= 120
    if "rapport" in normalized and "etat financier" not in normalized:
        score -= 40
    if "trimestriel" in normalized or "semestriel" in normalized:
        score -= 60
    return score


def parse_company_reports(
    client: httpx.Client,
    company: CompanyLink,
    years: set[int],
) -> list[ReportLink]:
    url = f"{company.url}?field_type_rapport_tid=57"
    soup = BeautifulSoup(fetch_html(client, url), "html.parser")
    reports: dict[str, ReportLink] = {}
    min_year = min(years)
    max_year = max(years)
    company_slug = company.url.rstrip("/").split("/")[-1]
    company_code = company_slug.split("-")[-1]
    for row in soup.select("div.view-content table tbody tr"):
        title_node = row.find("strong")
        link_node = row.find("a", href=True)
        if title_node is None or link_node is None:
            continue
        title = title_node.get_text(" ", strip=True)
        link = urljoin(BASE_URL, link_node["href"])
        candidate_years = extract_years(f"{title} {link}")
        hint_year = max(candidate_years) if candidate_years else None
        candidate = ReportLink(
            company_name=company.name,
            company_url=company.url,
            title=title,
            url=link,
            year=hint_year,
            score=report_score(title, hint_year or 0),
        )
        normalized_title_link = normalize_text(f"{title} {link.replace('_', ' ')}")
        if "semestre" in normalized_title_link or "trimestre" in normalized_title_link:
            continue
        if len(company_code) <= 3 and company_code.isalpha():
            if company_code not in normalized_title_link:
                continue
        if hint_year is not None and not (min_year - 1 <= hint_year <= max_year + 1):
            continue
        if candidate.score < 40:
            continue
        current = reports.get(link)
        if current is None or candidate.score > current.score:
            reports[link] = candidate
    return sorted(
        reports.values(),
        key=lambda item: ((item.year or 0), item.score, item.title),
        reverse=True,
    )


def download_file(client: httpx.Client, url: str, destination: Path) -> Path:
    if destination.exists():
        return destination
    response = client.get(url, headers={"User-Agent": USER_AGENT}, timeout=120.0, follow_redirects=True)
    response.raise_for_status()
    destination.write_bytes(response.content)
    return destination


def render_pdf_preview(pdf_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    command = ["qlmanage", "-t", "-s", "2400", "-o", str(output_dir), str(pdf_path)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    preview_path = output_dir / f"{pdf_path.name}.png"
    if not preview_path.exists():
        raise FileNotFoundError(f"Thumbnail not generated for {pdf_path}")
    return preview_path


def run_ocr(image_path: Path, ocr_path: Path) -> dict[str, Any]:
    if ocr_path.exists():
        return json.loads(ocr_path.read_text())
    env = dict(os.environ)
    env.update(
        {
            "SWIFT_MODULECACHE_PATH": "/tmp/swift-module-cache",
            "CLANG_MODULE_CACHE_PATH": "/tmp/clang-module-cache",
        }
    )
    result = subprocess.run(
        ["swift", str(SWIFT_SCRIPT), str(image_path)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    ocr_path.write_text(result.stdout)
    return json.loads(result.stdout)


def page_count(pdf_path: Path) -> int:
    with pdfplumber.open(pdf_path) as pdf:
        return len(pdf.pages)


def split_pdf_pages(pdf_path: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(output_dir.glob("page-*.pdf"))
    if existing:
        return existing
    env = dict(os.environ)
    env.update(
        {
            "SWIFT_MODULECACHE_PATH": "/tmp/swift-module-cache",
            "CLANG_MODULE_CACHE_PATH": "/tmp/clang-module-cache",
        }
    )
    subprocess.run(
        ["swift", str(SPLIT_SCRIPT), str(pdf_path), str(output_dir)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return sorted(output_dir.glob("page-*.pdf"))


def ocr_pdf_document(pdf_path: Path, cache_key: str) -> dict[str, Any]:
    pages = page_count(pdf_path)
    if pages <= 1:
        png_path = render_pdf_preview(pdf_path, PNG_DIR)
        ocr_path = OCR_DIR / f"{cache_key}.json"
        payload = run_ocr(png_path, ocr_path)
        if payload.get("pages"):
            payload["pages"][0]["page_number"] = 1
        return payload

    split_dir = CACHE_DIR / "split" / cache_key
    page_pdfs = split_pdf_pages(pdf_path, split_dir)[:10]
    combined_pages: list[dict[str, Any]] = []
    for index, page_pdf in enumerate(page_pdfs, start=1):
        png_path = render_pdf_preview(page_pdf, PNG_DIR / cache_key)
        ocr_path = OCR_DIR / cache_key / f"{page_pdf.stem}.json"
        ocr_path.parent.mkdir(parents=True, exist_ok=True)
        payload = run_ocr(png_path, ocr_path)
        if payload.get("pages"):
            page_payload = payload["pages"][0]
            page_payload["page_number"] = index
            combined_pages.append(page_payload)
    return {"source": str(pdf_path), "page_count": pages, "pages": combined_pages}


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


def row_numeric_candidates(tokens: list[OCRToken], label_token: OCRToken) -> list[OCRToken]:
    candidates: list[OCRToken] = []
    for token in tokens:
        if token.page != label_token.page:
            continue
        if token.x <= label_token.x + 0.03:
            continue
        if abs(token.y - label_token.y) > max(0.012, label_token.height * 1.5):
            continue
        if parse_amount(token.text) is None:
            continue
        candidates.append(token)
    return candidates


def pick_value_for_label(tokens: list[OCRToken], year_x_positions: list[float], labels: list[str]) -> float | None:
    normalized_labels = [normalize_text(label) for label in labels]
    for token in tokens:
        normalized = normalize_text(token.text)
        if not any(label in normalized for label in normalized_labels):
            continue
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
    candidates = [
        token
        for token in tokens
        if normalize_text(token.text) == "total" and token.x < 0.35 and 0.60 <= token.y <= 0.78
    ]
    for token in candidates:
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
    current_assets = pick_value_for_label(tokens, positions, ["Actif circulant", "Actifs courants"])
    if current_assets is None and any(value is not None for value in (inventories, receivables, cash_assets)):
        current_assets = sum(value or 0.0 for value in (inventories, receivables, cash_assets))

    financial_debts = pick_value_for_label(
        tokens,
        positions,
        ["Dettes financières", "Dettes financieres", "Emprunts et dettes financières"],
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
    if total_debts is None and total_assets is not None and equity is not None:
        total_debts = total_assets - equity

    current_liabilities = pick_value_for_label(tokens, positions, ["Passifs courants", "Passif circulant", "Passifs circulants"])
    if current_liabilities is None and any(value is not None for value in (operating_debts, cash_liabilities)):
        current_liabilities = sum(value or 0.0 for value in (operating_debts, cash_liabilities))

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


def export_dataframe(dataframe: pd.DataFrame, destination_csv: Path) -> None:
    dataframe.to_csv(destination_csv, index=False)
    try:
        dataframe.to_excel(destination_csv.with_suffix(".xlsx"), index=False)
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract BRVM listed-company financial metrics from BRVM reports.")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of issuers processed.")
    parser.add_argument("--years", nargs="*", type=int, default=DEFAULT_YEARS, help="Report years to extract.")
    args = parser.parse_args()

    ensure_dirs()
    years = set(args.years)

    rows: list[dict[str, Any]] = []
    with httpx.Client(verify=False) as client:
        companies = crawl_company_links(client)
        if args.limit is not None:
            companies = companies[: args.limit]

        for company in companies:
            reports = parse_company_reports(client, company, years)
            collected: dict[int, dict[str, Any]] = {}
            for index, report in enumerate(reports[:12], start=1):
                cache_key = f"{slugify(company.name)}-{report.year or 'unknown'}-{index}"
                suffix = Path(report.url).suffix or ".pdf"
                pdf_path = PDF_DIR / f"{cache_key}{suffix}"
                pdf_path = download_file(client, report.url, pdf_path)
                tokens = load_tokens(ocr_pdf_document(pdf_path, cache_key))
                detected_year = detect_report_year(tokens)
                if detected_year not in years or detected_year in collected:
                    continue
                metrics = extract_metrics(tokens, detected_year)
                row = {
                    "emetteur": company.name,
                    "company_url": company.url,
                    "report_year": detected_year,
                    "report_title": report.title,
                    "report_url": report.url,
                    "status": "ok",
                    **metrics,
                }
                if not any(value is not None for key, value in metrics.items() if not key.startswith("marge") and key not in {"roe", "roa", "ratio_endettement", "autonomie_financiere", "ratio_liquidite_generale"}):
                    row["status"] = "parsed_but_empty"
                collected[detected_year] = row
                if len(collected) == len(years):
                    break

            for year in sorted(years):
                rows.append(
                    collected.get(
                        year,
                        {
                            "emetteur": company.name,
                            "company_url": company.url,
                            "report_year": year,
                            "report_title": None,
                            "report_url": None,
                            "status": "missing_report",
                        },
                    )
                )

    dataframe = pd.DataFrame(rows)
    preferred_order = [
        "emetteur",
        "report_year",
        "status",
        "report_title",
        "report_url",
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
        "company_url",
    ]
    dataframe = dataframe[[column for column in preferred_order if column in dataframe.columns]]
    export_dataframe(dataframe, OUTPUT_DIR / "brvm_financials_2020_2025.csv")
    print(f"Wrote {len(dataframe)} rows to {OUTPUT_DIR / 'brvm_financials_2020_2025.csv'}")


if __name__ == "__main__":
    main()
