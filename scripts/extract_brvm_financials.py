from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import time
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
    publication_year: int | None = None


STOP_MATCH_TOKENS = {
    "africa",
    "bank",
    "cote",
    "ivoire",
    "societe",
    "société",
    "compagnie",
    "international",
}

KNOWN_REPORTS_BY_EMITTER: dict[str, list[dict[str, object]]] = {
    "ORANGE CI": [
        {
            "title": "ORANGE CI : Etats financiers consolides exercice 2022",
            "url": "https://www.brvm.org/sites/default/files/20230214_-_etats_financiers_consolides_exercice_2022_-_orange_ci.pdf",
            "year": 2022,
            "publication_year": 2023,
        },
        {
            "title": "ORANGE CI : Etats financiers - Exercice 2023",
            "url": "https://www.brvm.org/sites/default/files/20240221_-_resultats_financiers_consolides_2023_-_orange_ci.pdf",
            "year": 2023,
            "publication_year": 2024,
        },
        {
            "title": "ORANGE CI : Etats financiers - Exercice 2024",
            "url": "https://www.brvm.org/sites/default/files/20250221_-_etats_financiers_-_exercice_2024_-_orange_ci.pdf",
            "year": 2024,
            "publication_year": 2025,
        },
        {
            "title": "ORANGE CI : Etats financiers - Exercice 2025",
            "url": "https://www.brvm.org/sites/default/files/20260217_-_etats_financiers_-_exercice_2025_-_orange_ci.pdf",
            "year": 2025,
            "publication_year": 2026,
        },
    ],
    "AIR LIQUIDE CI": [
        {
            "title": "AIR LIQUIDE CI : Etats financiers exercice 2020",
            "url": "https://www.brvm.org/sites/default/files/20210428_-_etats_financiers_-_exercice_2020_-_air_liquide_ci_1.pdf",
            "year": 2020,
            "publication_year": 2021,
        },
    ],
    "VIVO ENERGY CI": [
        {
            "title": "VIVO ENERGY CI : Etats financiers exercice 2021",
            "url": "https://www.brvm.org/sites/default/files/20220906_-_etats_financiers_exercice_2021_-_vivo_energy_ci.pdf",
            "year": 2021,
            "publication_year": 2022,
        },
    ],
    "TOTAL SENEGAL S.A.": [
        {
            "title": "TOTALENERGIES MARKETING SN : Etats financiers IFRS - Exercice 2024",
            "url": "https://www.brvm.org/sites/default/files/20250502_-_etats_financiers_-_norme_ifrs_-_exercice_2024_-_totalenergies_marketing_sn.pdf",
            "year": 2024,
            "publication_year": 2025,
        },
        {
            "title": "TOTALENERGIES MARKETING SN : Etats financiers SYSCOHADA - Exercice 2025",
            "url": "https://www.brvm.org/sites/default/files/20260430_-_etats_financiers_syscohada_-_exercice_2025_-_totalenergies_marketing_sn.pdf",
            "year": 2025,
            "publication_year": 2026,
        },
    ],
}


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


def fold_text_for_search(value: str) -> str:
    value = value.replace("\u2019", "'").replace("\xa0", " ")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return value.lower()


def extract_years(text: str) -> list[int]:
    return [int(year) for year in re.findall(r"\b(20\d{2})\b", text)]


def infer_publication_date(url: str) -> str | None:
    match = re.search(r"/(\d{8})[^/]*$", url)
    if not match:
        return None
    raw = match.group(1)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def infer_publication_year(url: str) -> int | None:
    publication_date = infer_publication_date(url)
    if publication_date is None:
        return None
    return int(publication_date[:4])


def infer_fiscal_year(title: str, url: str) -> int | None:
    normalized_title = normalize_text(title)
    normalized_url = normalize_text(url.replace("_", " ").replace("-", " "))

    prioritized_patterns = [
        r"exercice\s+(20\d{2})",
        r"au\s+31\s+decembre\s+(20\d{2})",
        r"etats?\s+financiers?.*?(20\d{2})",
        r"comptes?.*?(20\d{2})",
    ]
    for pattern in prioritized_patterns:
        match = re.search(pattern, normalized_title)
        if match:
            return int(match.group(1))

    title_years = extract_years(normalized_title)
    if title_years:
        return max(title_years)

    url_years = extract_years(normalized_url)
    if not url_years:
        return None

    publish_year = min(url_years)
    return publish_year - 1 if publish_year >= 2001 else publish_year


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


def parse_signed_amount(text: str) -> float | None:
    stripped = text.strip()
    if not stripped:
        return None
    negative = stripped.startswith("(") and stripped.endswith(")")
    value = parse_amount(stripped.strip("()"))
    if value is None:
        return None
    return -value if negative else value


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


def ensure_dirs() -> None:
    for path in (CACHE_DIR, PDF_DIR, PNG_DIR, OCR_DIR, OUTPUT_DIR):
        path.mkdir(parents=True, exist_ok=True)


def fetch_html(client: httpx.Client, url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = client.get(url, headers={"User-Agent": USER_AGENT}, timeout=60.0, follow_redirects=True)
            response.raise_for_status()
            return response.text
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt == 3:
                break
            time.sleep(min(5.0, attempt * 1.5))
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Failed to fetch HTML for {url}")


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


def crawl_global_report_links(
    client: httpx.Client,
    years: set[int],
    max_pages: int = 80,
) -> list[ReportLink]:
    """
    Crawl global BRVM annual-report pages.

    Some official reports are published as article nodes under
    `/fr/type-document/rapports-annuels` but do not appear in the issuer tab
    `rapports-societe-cotes/<issuer>?field_type_rapport_tid=57`.
    """
    reports: dict[str, ReportLink] = {}
    base_url = f"{BASE_URL}/fr/type-document/rapports-annuels"
    min_year = min(years)
    max_year = max(years)

    for page in range(max(0, max_pages)):
        url = base_url if page == 0 else f"{base_url}?page={page}"
        soup = BeautifulSoup(fetch_html(client, url), "html.parser")
        found_on_page = 0

        for anchor in soup.select("a[href^='/fr/']"):
            title = anchor.get_text(" ", strip=True)
            if not title or title.lower().startswith("lire la suite"):
                continue

            article_url = urljoin(BASE_URL, anchor.get("href", ""))
            if "/fr/type-document/" in article_url or "/fr/rapports-" in article_url:
                continue

            normalized = normalize_text(title)
            if not any(
                marker in normalized
                for marker in ("etat financier", "etats financiers", "rapport", "activite", "annuel", "exercice")
            ):
                continue

            fiscal_year = infer_fiscal_year(title, article_url)
            if fiscal_year is None or not (min_year <= fiscal_year <= max_year):
                continue

            score = report_score(title, fiscal_year)
            if score < 20:
                continue

            reports[article_url] = ReportLink(
                company_name="",
                company_url=article_url,
                title=title,
                url=article_url,
                year=fiscal_year,
                score=score,
                publication_year=infer_publication_year(article_url),
            )
            found_on_page += 1

    return sorted(
        reports.values(),
        key=lambda item: ((item.year or 0), item.score, item.title),
        reverse=True,
    )


def match_global_reports(
    company: CompanyLink,
    reports: list[ReportLink],
    years: set[int],
) -> list[ReportLink]:
    normalized_company = normalize_text(company.name)
    company_tokens = _meaningful_company_tokens(normalized_company)
    matched: dict[str, ReportLink] = {}

    for report in reports:
        if report.year not in years:
            continue
        normalized_title = normalize_text(report.title)
        if not _title_matches_company(normalized_title, normalized_company, company_tokens):
            continue
        matched[report.url] = ReportLink(
            company_name=company.name,
            company_url=company.url,
            title=report.title,
            url=report.url,
            year=report.year,
            score=report.score,
            publication_year=report.publication_year,
        )

    return sorted(matched.values(), key=lambda item: ((item.year or 0), item.score), reverse=True)


def known_reports_for_company(company: CompanyLink, years: set[int]) -> list[ReportLink]:
    reports: list[ReportLink] = []
    normalized_company = normalize_text(company.name)
    for emitter_name, known_reports in KNOWN_REPORTS_BY_EMITTER.items():
        normalized_emitter = normalize_text(emitter_name)
        if normalized_company != normalized_emitter:
            continue
        for raw_report in known_reports:
            year = raw_report.get("year")
            if not isinstance(year, int) or year not in years:
                continue
            title = str(raw_report["title"])
            reports.append(
                ReportLink(
                    company_name=company.name,
                    company_url=company.url,
                    title=title,
                    url=str(raw_report["url"]),
                    year=year,
                    score=report_score(title, year) + 200,
                    publication_year=raw_report.get("publication_year")
                    if isinstance(raw_report.get("publication_year"), int)
                    else None,
                )
            )
    return reports


def _meaningful_company_tokens(normalized_company: str) -> list[str]:
    return [
        token
        for token in normalized_company.split()
        if len(token) >= 4 and token not in STOP_MATCH_TOKENS
    ]


def _title_matches_company(
    normalized_title: str,
    normalized_company: str,
    company_tokens: list[str],
) -> bool:
    if normalized_company and normalized_company in normalized_title:
        return True

    # Keep short official names safe: CIE CI must not match SICABLE CI.
    short_company_aliases = {
        "cie ci": ("cie",),
        "sib": ("sib",),
        "sgci": ("societe generale", "sgci"),
        "smb": ("smb",),
        "nsbc": ("nsia", "nsbc"),
    }
    for alias, title_markers in short_company_aliases.items():
        if normalized_company == alias:
            title_tokens = set(normalized_title.split())
            return any(
                (marker in normalized_title if " " in marker else marker in title_tokens)
                for marker in title_markers
            )

    if not company_tokens:
        return False

    overlap = sum(1 for token in company_tokens if token in normalized_title)
    return overlap >= min(2, len(company_tokens))


def resolve_report_download_url(client: httpx.Client, url: str) -> str:
    if ".pdf" in url.lower():
        return url

    soup = BeautifulSoup(fetch_html(client, url), "html.parser")
    pdf_links: list[str] = []
    for anchor in soup.select("a[href]"):
        href = urljoin(url, anchor.get("href", ""))
        if ".pdf" in href.lower():
            pdf_links.append(href)

    if not pdf_links:
        raise RuntimeError(f"No PDF found on BRVM article page: {url}")
    return pdf_links[0]


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


def count_core_metrics(metrics: dict[str, float | None]) -> int:
    core_fields = (
        "resultat_operationnel",
        "resultat_net",
        "chiffre_affaires",
        "capitaux_propres",
        "total_actif",
        "dettes_totales",
        "actifs_courants",
        "passifs_courants",
    )
    return sum(value is not None for key, value in metrics.items() if key in core_fields)


def classify_missing_year_reason(
    available_reports: list[ReportLink],
    fiscal_year: int,
) -> tuple[str, str]:
    same_fiscal_year = [report for report in available_reports if report.year == fiscal_year]
    if same_fiscal_year:
        return (
            "report_candidates_unusable",
            "; ".join(
                f"{report.title} [score={report.score}]"
                for report in sorted(same_fiscal_year, key=lambda item: item.score, reverse=True)[:3]
            ),
        )

    nearby_reports = [
        report for report in available_reports if report.year is not None and abs(report.year - fiscal_year) <= 1
    ]
    if nearby_reports:
        return (
            "nearest_report_is_different_fiscal_year",
            "; ".join(
                f"fy={report.year} pub={report.publication_year} title={report.title} [score={report.score}]"
                for report in sorted(
                    nearby_reports,
                    key=lambda item: (abs((item.year or fiscal_year) - fiscal_year), -item.score),
                )[:3]
            ),
        )

    if available_reports:
        return (
            "no_candidate_for_fiscal_year",
            "; ".join(
                f"fy={report.year} pub={report.publication_year} title={report.title} [score={report.score}]"
                for report in sorted(available_reports, key=lambda item: (-item.score, item.title))[:3]
            ),
        )

    return ("no_reports_found_on_company_page", "")


def parse_company_reports(
    client: httpx.Client,
    company: CompanyLink,
    years: set[int],
) -> list[ReportLink]:
    reports: dict[str, ReportLink] = {}
    min_year = min(years)
    max_year = max(years)
    company_slug = company.url.rstrip("/").split("/")[-1]
    company_code = company_slug.split("-")[-1]
    page_number = 0
    max_pages = 8
    while page_number < max_pages:
        suffix = f"?field_type_rapport_tid=57&page={page_number}" if page_number else "?field_type_rapport_tid=57"
        url = f"{company.url}{suffix}"
        soup = BeautifulSoup(fetch_html(client, url), "html.parser")
        rows = soup.select("div.view-content table tbody tr")
        if not rows:
            break
        for row in rows:
            title_node = row.find("strong")
            link_node = row.find("a", href=True)
            if title_node is None or link_node is None:
                continue
            title = title_node.get_text(" ", strip=True)
            link = urljoin(BASE_URL, link_node["href"])
            hint_year = infer_fiscal_year(title, link)
            candidate = ReportLink(
                company_name=company.name,
                company_url=company.url,
                title=title,
                url=link,
                year=hint_year,
                score=report_score(title, hint_year or 0),
                publication_year=infer_publication_year(link),
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
        has_next = soup.select_one("ul.pagination li.next a") is not None
        if not has_next:
            break
        page_number += 1
    return sorted(
        reports.values(),
        key=lambda item: ((item.year or 0), item.score, item.title),
        reverse=True,
    )


def merge_report_candidates(*groups: list[ReportLink]) -> list[ReportLink]:
    merged: dict[tuple[int | None, str], ReportLink] = {}
    for group in groups:
        for report in group:
            key = (report.year, report.url)
            current = merged.get(key)
            if current is None or report.score > current.score:
                merged[key] = report
    return sorted(
        merged.values(),
        key=lambda item: ((item.year or 0), item.score, item.title),
        reverse=True,
    )


def download_file(client: httpx.Client, url: str, destination: Path) -> Path:
    if destination.exists():
        return destination
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = client.get(url, headers={"User-Agent": USER_AGENT}, timeout=120.0, follow_redirects=True)
            response.raise_for_status()
            destination.write_bytes(response.content)
            return destination
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt == 3:
                break
            time.sleep(min(8.0, attempt * 2.0))
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Failed to download file for {url}")


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
    page_pdfs = split_pdf_pages(pdf_path, split_dir)
    selected_page_pdfs = page_pdfs[:10]
    if len(page_pdfs) > 10:
        selected_page_pdfs.extend(page_pdfs[-10:])
        deduped: dict[str, Path] = {}
        for page_pdf in selected_page_pdfs:
            deduped[page_pdf.name] = page_pdf
        selected_page_pdfs = [deduped[name] for name in sorted(deduped)]
    combined_pages: list[dict[str, Any]] = []
    for page_pdf in selected_page_pdfs:
        match = re.search(r"page-(\d+)\.pdf$", page_pdf.name)
        page_number = int(match.group(1)) if match else 1
        png_path = render_pdf_preview(page_pdf, PNG_DIR / cache_key)
        ocr_path = OCR_DIR / cache_key / f"{page_pdf.stem}.json"
        ocr_path.parent.mkdir(parents=True, exist_ok=True)
        payload = run_ocr(png_path, ocr_path)
        if payload.get("pages"):
            page_payload = payload["pages"][0]
            page_payload["page_number"] = page_number
            combined_pages.append(page_payload)
    return {"source": str(pdf_path), "page_count": pages, "pages": combined_pages}


def pdf_unit_multiplier(text: str) -> float:
    normalized = normalize_text(text)
    if "en milliards fcfa" in normalized or "milliards fcfa" in normalized:
        return 1_000_000_000.0
    if "en millions fcfa" in normalized or "millions fcfa" in normalized:
        return 1_000_000.0
    if "en milliers fcfa" in normalized or "milliers fcfa" in normalized:
        return 1_000.0
    return 1.0


def extract_pdf_text_pages(pdf_path: Path) -> list[tuple[int, str]]:
    pages: list[tuple[int, str]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append((page_number, text))
    return pages


def parse_value_from_table_cell(cell: str | None) -> float | None:
    if not cell:
        return None
    matches = re.findall(r"\(?-?\d+(?: \d{3})*(?:[.,]\d+)?\)?", cell)
    cleaned = [
        match for match in matches
        if not re.fullmatch(r"20\d{2}", match.strip())
        and not re.fullmatch(r"\d+\.\d+", match.strip())
    ]
    if not cleaned:
        return None
    return parse_signed_amount(cleaned[-1])


def find_table_year_column(table: list[list[str | None]], report_year: int) -> int | None:
    target = str(report_year)
    for row in table[:3]:
        for index, cell in enumerate(row):
            if not cell:
                continue
            lines = [part.strip() for part in str(cell).splitlines() if part.strip()]
            if any(part == target or part.replace(" ", "") == target for part in lines):
                return index
    for row in table[:3]:
        for index, cell in enumerate(row):
            if cell and re.search(rf"\b{re.escape(target)}\b", str(cell)):
                return index
    return None


def extract_value_from_pdf_tables(
    pdf_path: Path,
    *,
    report_year: int,
    page_markers: list[str],
    label_markers: list[str],
    excluded_terms: list[str] | None = None,
) -> float | None:
    with pdfplumber.open(pdf_path) as pdf:
        candidates: list[tuple[int, int, list[list[str | None]], str]] = []
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            score = page_matches_markers(text, page_markers)
            if score <= 0:
                continue
            table = page.extract_table()
            if not table:
                continue
            candidates.append((score, page_number, table, text))

        for _, _, table, page_text in sorted(candidates, key=lambda item: (-item[0], -item[1])):
            target_column = find_table_year_column(table, report_year)
            if target_column is None:
                continue
            multiplier = pdf_unit_multiplier(page_text)
            line_candidates: list[tuple[int, list[str | None]]] = []
            for row in table:
                label = str(row[0] or "").strip()
                if not label:
                    continue
                normalized_label = normalize_text(label)
                if excluded_terms and any(normalize_text(term) in normalized_label for term in excluded_terms):
                    continue
                score = line_label_score(label, label_markers)
                if score is None:
                    continue
                line_candidates.append((score, row))

            for _, row in sorted(line_candidates, key=lambda item: -item[0]):
                if target_column < len(row):
                    value = parse_value_from_table_cell(row[target_column])
                    if value is not None:
                        return value * multiplier
                value = parse_value_from_table_cell(row[0])
                if value is not None:
                    return value * multiplier
    return None


def extract_page_years(text: str) -> list[int]:
    seen: list[int] = []
    for match in re.finditer(r"\b(20\d{2})\b", text):
        year = int(match.group(1))
        if year not in seen:
            seen.append(year)
    return seen


def page_matches_markers(text: str, markers: list[str]) -> int:
    normalized = normalize_text(text)
    return sum(1 for marker in markers if normalize_text(marker) in normalized)


def extract_line_values(line: str, year_count: int) -> list[float]:
    raw_matches = re.findall(r"\(?-?\d+(?: \d{3})*(?:[.,]\d+)?\)?", line)
    if len(raw_matches) == 1 and year_count > 1:
        stripped = raw_matches[0].strip().strip("()")
        if "," not in stripped and "." not in stripped:
            parts = stripped.split()
            if len(parts) % year_count == 0:
                group_size = len(parts) // year_count
                grouped_values: list[float] = []
                for index in range(year_count):
                    group = " ".join(parts[index * group_size : (index + 1) * group_size])
                    parsed = parse_signed_amount(group)
                    if parsed is not None:
                        grouped_values.append(parsed)
                if len(grouped_values) == year_count:
                    return grouped_values

    values: list[float] = []
    for raw in raw_matches:
        token = raw.strip()
        if re.fullmatch(r"20\d{2}", token):
            continue
        if re.fullmatch(r"\d+\.\d+", token):
            continue
        value = parse_signed_amount(token)
        if value is None:
            continue
        values.append(value)
    if len(values) > year_count:
        values = values[:year_count]
    return values


def line_label_score(line: str, label_markers: list[str]) -> int | None:
    normalized_line = normalize_text(line)
    best_score: int | None = None
    for index, marker in enumerate(label_markers):
        normalized_marker = normalize_text(marker)
        score: int | None = None
        if normalized_line == normalized_marker:
            score = 120 - index
        elif normalized_line.startswith(f"{normalized_marker} "):
            score = 100 - index
        elif normalized_marker in normalized_line:
            score = 60 - index
        if score is None:
            continue
        if best_score is None or score > best_score:
            best_score = score
    return best_score


def trim_line_to_marker(line: str, label_markers: list[str]) -> str:
    folded_line = fold_text_for_search(line)
    best_start: int | None = None
    best_length = 0
    for marker in label_markers:
        folded_marker = fold_text_for_search(marker)
        position = folded_line.find(folded_marker)
        if position == -1:
            continue
        if best_start is None or position < best_start or (position == best_start and len(folded_marker) > best_length):
            best_start = position
            best_length = len(folded_marker)
    if best_start is None:
        return line
    return line[best_start + best_length :]


def extract_value_from_statement_pages(
    pages: list[tuple[int, str]],
    *,
    report_year: int,
    page_markers: list[str],
    label_markers: list[str],
    excluded_terms: list[str] | None = None,
) -> float | None:
    scored_pages = [
        (page_matches_markers(text, page_markers), page_number, text)
        for page_number, text in pages
    ]
    scored_pages = [item for item in scored_pages if item[0] > 0] or [
        (0, page_number, text) for page_number, text in pages
    ]
    for _, _, text in sorted(scored_pages, key=lambda item: (-item[0], -item[1])):
        page_years = [year for year in extract_page_years(text) if 2000 <= year <= 2035]
        if report_year not in page_years:
            continue
        year_index = page_years.index(report_year)
        year_count = len(page_years)
        multiplier = pdf_unit_multiplier(text)
        matching_lines: list[tuple[int, str]] = []
        for line in text.splitlines():
            normalized_line = normalize_text(line)
            if excluded_terms and any(normalize_text(term) in normalized_line for term in excluded_terms):
                continue
            score = line_label_score(line, label_markers)
            if score is None:
                continue
            matching_lines.append((score, line))
        for _, line in sorted(matching_lines, key=lambda item: -item[0]):
            values = extract_line_values(trim_line_to_marker(line, label_markers), year_count)
            if year_index < len(values):
                return values[year_index] * multiplier
    return None


def extract_metrics_from_pdf_text(pdf_path: Path, report_year: int) -> dict[str, float | None]:
    pages = extract_pdf_text_pages(pdf_path)
    if not pages:
        return {}

    revenue = extract_value_from_statement_pages(
        pages,
        report_year=report_year,
        page_markers=["compte de résultat", "compte de resultat", "ifrs_compte de résultat", "résultat net de l'ensemble consolidé", "resultat net de l'ensemble consolide"],
        label_markers=["chiffre d'affaires", "chiffre d’affaires", "produit net bancaire"],
    )
    operating_result = extract_value_from_statement_pages(
        pages,
        report_year=report_year,
        page_markers=["compte de résultat", "compte de resultat", "ifrs_compte de résultat", "résultat net de l'ensemble consolidé", "resultat net de l'ensemble consolide"],
        label_markers=["résultat d'exploitation", "resultat d'exploitation", "résultat d’exploitation", "résultat d'exploitation", "résultat opérationnel", "resultat operationnel"],
    )
    net_income = extract_value_from_statement_pages(
        pages,
        report_year=report_year,
        page_markers=["compte de résultat", "compte de resultat", "ifrs_compte de résultat", "résultats financiers consolidés"],
        label_markers=["résultat net de l'ensemble consolidé", "resultat net de l'ensemble consolide", "résultat net", "resultat net"],
    )
    total_assets = extract_value_from_statement_pages(
        pages,
        report_year=report_year,
        page_markers=["bilan - actif", "ifrs_actif", "total de l'actif", "total de l’actif"],
        label_markers=["total de l'actif", "total de l’actif", "total du bilan", "total actif"],
        excluded_terms=["non courant", "courant"],
    )
    current_assets = extract_value_from_statement_pages(
        pages,
        report_year=report_year,
        page_markers=["bilan - actif", "ifrs_actif", "actif courant", "actif circulant"],
        label_markers=["total de l'actif courant", "total de l’actif courant", "actif circulant", "actifs courants", "total actif circulant"],
    )
    equity = extract_value_from_statement_pages(
        pages,
        report_year=report_year,
        page_markers=["bilan - passif", "ifrs_passif", "total capitaux propres"],
        label_markers=["total capitaux propres"],
    )
    current_liabilities = extract_value_from_statement_pages(
        pages,
        report_year=report_year,
        page_markers=["bilan - passif", "ifrs_passif", "passifs courants", "passif circulant"],
        label_markers=["total des passifs courants", "passifs courants", "total passif circulant"],
    )

    total_debts = None
    if total_assets is not None and equity is not None:
        total_debts = total_assets - equity

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


def extract_metrics_from_pdf_tables(pdf_path: Path, report_year: int) -> dict[str, float | None]:
    revenue = extract_value_from_pdf_tables(
        pdf_path,
        report_year=report_year,
        page_markers=["compte de résultat", "compte de resultat", "ifrs_compte de résultat", "résultat net de l'ensemble consolidé"],
        label_markers=["chiffre d'affaires", "chiffre d’affaires", "produit net bancaire"],
    )
    operating_result = extract_value_from_pdf_tables(
        pdf_path,
        report_year=report_year,
        page_markers=["compte de résultat", "compte de resultat", "ifrs_compte de résultat", "résultat net de l'ensemble consolidé"],
        label_markers=["résultat d'exploitation", "résultat d’exploitation", "resultat d'exploitation", "résultat opérationnel", "resultat operationnel"],
    )
    net_income = extract_value_from_pdf_tables(
        pdf_path,
        report_year=report_year,
        page_markers=["compte de résultat", "compte de resultat", "ifrs_compte de résultat", "résultat net de l'ensemble consolidé"],
        label_markers=["résultat net de l'ensemble consolidé", "resultat net de l'ensemble consolide", "résultat net", "resultat net"],
    )
    total_assets = extract_value_from_pdf_tables(
        pdf_path,
        report_year=report_year,
        page_markers=["bilan - actif", "ifrs_actif", "total de l'actif", "total de l’actif"],
        label_markers=["total de l'actif", "total de l’actif", "total du bilan", "total actif"],
        excluded_terms=["non courant", "courant"],
    )
    current_assets = extract_value_from_pdf_tables(
        pdf_path,
        report_year=report_year,
        page_markers=["bilan - actif", "ifrs_actif", "actif courant", "actif circulant"],
        label_markers=["total de l'actif courant", "total de l’actif courant", "actif circulant", "actifs courants", "total actif circulant"],
    )
    equity = extract_value_from_pdf_tables(
        pdf_path,
        report_year=report_year,
        page_markers=["bilan - passif", "ifrs_passif", "total capitaux propres"],
        label_markers=["total capitaux propres"],
    )
    current_liabilities = extract_value_from_pdf_tables(
        pdf_path,
        report_year=report_year,
        page_markers=["bilan - passif", "ifrs_passif", "passifs courants", "passif circulant"],
        label_markers=["total des passifs courants", "passifs courants", "total passif circulant"],
    )

    total_debts = None
    if total_assets is not None and equity is not None:
        total_debts = total_assets - equity

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
    target = str(year)
    positions = sorted(
        token.x
        for token in tokens
        if normalize_text(token.text) == target or target in normalize_text(token.text)
    )
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


def pick_value_for_label(
    tokens: list[OCRToken],
    year_x_positions: list[float],
    labels: list[str],
    *,
    prefer_non_zero: bool = False,
) -> float | None:
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
        if prefer_non_zero and value == 0.0:
            non_zero_candidates = [
                candidate
                for candidate in candidates
                if parse_amount(candidate.text) not in {None, 0.0}
            ]
            if non_zero_candidates:
                fallback = min(
                    non_zero_candidates,
                    key=lambda item: (
                        abs(item.x - chosen.x),
                        abs(item.x - target_x) if target_positions else item.x,
                    ),
                )
                fallback_value = parse_amount(fallback.text)
                if fallback_value is not None:
                    value = fallback_value
        if value is not None:
            return value
    return None


def pick_total_assets(tokens: list[OCRToken], year_x_positions: list[float]) -> float | None:
    labelled_tokens = []
    for token in tokens:
        normalized = normalize_text(token.text)
        score = None
        if normalized in {
            "total actif",
            "total de l'actif",
            "total bilan",
            "total passif",
            "total du passif",
            "total passif et capitaux propres",
            "total du passif et des capitaux propres",
        }:
            score = 100
        elif (
            (
                "total actif" in normalized
                or "total de l'actif" in normalized
                or "total bilan" in normalized
                or "total du passif" in normalized
                or "total passif et capitaux propres" in normalized
            )
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


def pick_total_passif(tokens: list[OCRToken], year_x_positions: list[float]) -> float | None:
    labelled_tokens = []
    for token in tokens:
        normalized = normalize_text(token.text)
        score = None
        if normalized in {
            "total du passif",
            "total passif",
            "total du passif et des capitaux propres",
            "total passif et capitaux propres",
        }:
            score = 100
        elif "total du passif" in normalized or "total passif" in normalized:
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


def is_bank_report(tokens: list[OCRToken]) -> bool:
    bank_markers = (
        "produit net bancaire",
        "creances interbancaires et assimilees",
        "creances bancaires et assimilees",
        "dettes interbancaires et assimilees",
        "capitaux propres et ressources assimilees",
    )
    normalized_texts = {normalize_text(token.text) for token in tokens}
    return any(any(marker in text for marker in bank_markers) for text in normalized_texts)


def sanitize_bank_metrics(
    metrics: dict[str, float | None],
    *,
    total_passif: float | None,
) -> dict[str, float | None]:
    sanitized = metrics.copy()
    equity = sanitized.get("capitaux_propres")
    total_assets = sanitized.get("total_actif")
    total_debts = sanitized.get("dettes_totales")
    revenue = sanitized.get("chiffre_affaires")

    if revenue is not None and equity is not None and revenue == equity:
        sanitized["chiffre_affaires"] = None
        revenue = None

    if total_assets is not None and equity is not None and total_assets < equity:
        replacement_assets = total_passif if total_passif is not None and total_passif >= equity else None
        sanitized["total_actif"] = replacement_assets
        total_assets = replacement_assets

    if total_debts is not None and total_debts < 0:
        if total_assets is not None and equity is not None and total_assets >= equity:
            sanitized["dettes_totales"] = total_assets - equity
        else:
            sanitized["dettes_totales"] = None
        total_debts = sanitized["dettes_totales"]

    if total_assets is not None and equity is not None and total_debts is not None:
        balance_gap = abs((equity + total_debts) - total_assets) / max(abs(total_assets), 1.0)
        if balance_gap > 0.5:
            sanitized["dettes_totales"] = None
            if total_passif is not None and equity is not None and total_passif >= equity:
                sanitized["total_actif"] = total_passif
            else:
                sanitized["total_actif"] = None

    sanitized["marge_operationnelle"] = safe_divide(sanitized.get("resultat_operationnel"), sanitized.get("chiffre_affaires"))
    sanitized["marge_nette"] = safe_divide(sanitized.get("resultat_net"), sanitized.get("chiffre_affaires"))
    sanitized["roe"] = safe_divide(sanitized.get("resultat_net"), sanitized.get("capitaux_propres"))
    sanitized["roa"] = safe_divide(sanitized.get("resultat_net"), sanitized.get("total_actif"))
    sanitized["ratio_endettement"] = safe_divide(sanitized.get("dettes_totales"), sanitized.get("capitaux_propres"))
    sanitized["autonomie_financiere"] = safe_divide(sanitized.get("capitaux_propres"), sanitized.get("total_actif"))
    sanitized["ratio_liquidite_generale"] = safe_divide(sanitized.get("actifs_courants"), sanitized.get("passifs_courants"))
    return sanitized


def detect_unit_from_tokens(tokens: list[OCRToken]) -> float:
    """Detect FCFA unit multiplier from OCR token text (En millions FCFA etc.)."""
    full_text = " ".join(token.text for token in tokens)
    return pdf_unit_multiplier(full_text)


def apply_unit_multiplier(metrics: dict[str, float | None], multiplier: float) -> dict[str, float | None]:
    """Apply unit multiplier to all raw monetary fields (not ratios)."""
    if multiplier == 1.0:
        return metrics
    monetary_fields = (
        "resultat_operationnel", "resultat_net", "chiffre_affaires",
        "capitaux_propres", "total_actif", "dettes_totales",
        "actifs_courants", "passifs_courants",
    )
    result = metrics.copy()
    for field in monetary_fields:
        if result.get(field) is not None:
            result[field] = result[field] * multiplier
    return result


def extract_metrics(tokens: list[OCRToken], report_year: int) -> dict[str, float | None]:
    bank_report = is_bank_report(tokens)
    unit_multiplier = detect_unit_from_tokens(tokens)
    positions = year_positions(tokens, report_year)
    revenue = pick_value_for_label(
        tokens,
        positions,
        [
            "Chiffre d'affaires",
            "Chiffre d affaires",
            "Produit net bancaire",
        ],
        prefer_non_zero=True,
    )
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
    total_passif = pick_total_passif(tokens, positions)
    if total_assets is None:
        total_assets = total_passif

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
    if total_debts is None and total_passif is not None and equity is not None:
        total_debts = total_passif - equity
    if total_debts is None and total_assets is not None and equity is not None:
        total_debts = total_assets - equity
    if total_assets is None and total_debts is not None and equity is not None:
        total_assets = total_debts + equity
    if total_assets is not None and total_debts is not None and equity is not None:
        reconstructed_assets = total_debts + equity
        if reconstructed_assets > total_assets:
            total_assets = reconstructed_assets

    raw_metrics: dict[str, float | None] = {
        "resultat_operationnel": operating_result,
        "resultat_net": net_income,
        "chiffre_affaires": revenue,
        "capitaux_propres": equity,
        "total_actif": total_assets,
        "dettes_totales": total_debts,
        "actifs_courants": current_assets,
        "passifs_courants": current_liabilities,
    }
    raw_metrics = apply_unit_multiplier(raw_metrics, unit_multiplier)
    metrics: dict[str, float | None] = raw_metrics
    metrics["marge_operationnelle"] = safe_divide(metrics["resultat_operationnel"], metrics["chiffre_affaires"])
    metrics["marge_nette"] = safe_divide(metrics["resultat_net"], metrics["chiffre_affaires"])
    metrics["roe"] = safe_divide(metrics["resultat_net"], metrics["capitaux_propres"])
    metrics["roa"] = safe_divide(metrics["resultat_net"], metrics["total_actif"])
    metrics["ratio_endettement"] = safe_divide(metrics["dettes_totales"], metrics["capitaux_propres"])
    metrics["autonomie_financiere"] = safe_divide(metrics["capitaux_propres"], metrics["total_actif"])
    metrics["ratio_liquidite_generale"] = safe_divide(metrics["actifs_courants"], metrics["passifs_courants"])
    if bank_report:
        metrics = sanitize_bank_metrics(metrics, total_passif=total_passif * unit_multiplier if total_passif is not None else None)
    return metrics


def detect_report_year(tokens: list[OCRToken]) -> int | None:
    years: list[int] = []
    for token in tokens:
        years.extend(extract_years(token.text))
    years = [year for year in years if 2000 <= year <= 2035]
    if not years:
        return None
    return max(years)


def resolve_report_year(report: ReportLink, tokens: list[OCRToken], expected_years: set[int]) -> int | None:
    if report.year is not None and report.year not in expected_years:
        return None
    hinted_year = report.year if report.year in expected_years else None
    detected_year = detect_report_year(tokens)
    if detected_year in expected_years and detected_year == hinted_year:
        return detected_year
    if hinted_year is not None:
        return hinted_year
    if detected_year in expected_years:
        return detected_year
    return None


def export_dataframe(dataframe: pd.DataFrame, destination_csv: Path) -> None:
    dataframe.to_csv(destination_csv, index=False)
    try:
        dataframe.to_excel(destination_csv.with_suffix(".xlsx"), index=False)
    except Exception:
        pass


def load_existing_rows(destination_csv: Path) -> list[dict[str, Any]]:
    if not destination_csv.exists():
        return []
    dataframe = pd.read_csv(destination_csv)
    return dataframe.to_dict(orient="records")


def merge_rows(existing_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, int], dict[str, Any]] = {}
    for row in existing_rows + new_rows:
        fiscal_year = row.get("fiscal_year")
        emetteur = row.get("emetteur")
        if emetteur is None or pd.isna(fiscal_year):
            continue
        merged[(str(emetteur), int(float(fiscal_year)))] = row
    return list(merged.values())


def finalize_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    dataframe = pd.DataFrame(rows)
    preferred_order = [
        "emetteur",
        "fiscal_year",
        "report_year",
        "publication_date",
        "status",
        "status_reason",
        "diagnostic",
        "core_metrics_count",
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
    if dataframe.empty:
        return dataframe
    dataframe = dataframe[[column for column in preferred_order if column in dataframe.columns]]
    if {"emetteur", "fiscal_year"}.issubset(dataframe.columns):
        dataframe = dataframe.sort_values(["emetteur", "fiscal_year"]).reset_index(drop=True)
    return dataframe


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract BRVM listed-company financial metrics from BRVM reports.")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of issuers processed.")
    parser.add_argument("--years", nargs="*", type=int, default=DEFAULT_YEARS, help="Report years to extract.")
    parser.add_argument("--start-index", type=int, default=0, help="Zero-based start index in the issuer list.")
    parser.add_argument("--company-contains", type=str, default=None, help="Only process issuers whose name contains this text.")
    parser.add_argument("--checkpoint-every", type=int, default=1, help="Write partial CSV every N issuers.")
    parser.add_argument("--global-report-pages", type=int, default=80, help="Pages globales BRVM rapports annuels a crawler.")
    args = parser.parse_args()

    ensure_dirs()
    years = set(args.years)
    checkpoint_every = max(1, args.checkpoint_every)
    output_path = OUTPUT_DIR / "brvm_financials_2020_2025.csv"
    partial_run = args.start_index != 0 or args.limit is not None or args.company_contains is not None

    rows: list[dict[str, Any]] = load_existing_rows(output_path) if partial_run else []
    with httpx.Client(verify=False, timeout=120.0, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}) as client:
        companies = crawl_company_links(client)
        global_reports = crawl_global_report_links(
            client,
            years,
            max_pages=args.global_report_pages,
        )
        if args.company_contains:
            needle = normalize_text(args.company_contains)
            companies = [company for company in companies if needle in normalize_text(company.name)]
        if args.start_index:
            companies = companies[args.start_index :]
        if args.limit is not None:
            companies = companies[: args.limit]

        for company_index, company in enumerate(companies, start=1):
            try:
                reports = merge_report_candidates(
                    known_reports_for_company(company, years),
                    parse_company_reports(client, company, years),
                    match_global_reports(company, global_reports, years),
                )
            except Exception as exc:
                reports = []
                for year in sorted(years):
                    rows.append(
                        {
                            "emetteur": company.name,
                            "company_url": company.url,
                            "fiscal_year": year,
                            "report_year": None,
                            "publication_date": None,
                            "report_title": None,
                            "report_url": None,
                            "status": "company_error",
                            "status_reason": type(exc).__name__,
                            "diagnostic": str(exc),
                            "core_metrics_count": 0,
                        }
                    )
                if company_index % checkpoint_every == 0:
                    export_dataframe(finalize_dataframe(merge_rows([], rows)), output_path)
                continue
            collected: dict[int, dict[str, Any]] = {}
            for index, report in enumerate(reports[:12], start=1):
                try:
                    if report.year in years and report.year in collected:
                        continue
                    cache_key = f"{slugify(company.name)}-{report.year or 'unknown'}-{index}"
                    suffix = Path(report.url).suffix or ".pdf"
                    pdf_path = PDF_DIR / f"{cache_key}{suffix}"
                    download_url = resolve_report_download_url(client, report.url)
                    pdf_path = download_file(client, download_url, pdf_path)

                    resolved_year = report.year if report.year in years else None
                    metrics: dict[str, float | None] = {}
                    if resolved_year is not None:
                        metrics = extract_metrics_from_pdf_tables(pdf_path, resolved_year)
                        if count_core_metrics(metrics) < 4:
                            pdf_text_metrics = extract_metrics_from_pdf_text(pdf_path, resolved_year)
                            if count_core_metrics(pdf_text_metrics) > count_core_metrics(metrics):
                                metrics = pdf_text_metrics

                    tokens: list[OCRToken] = []
                    if resolved_year is None or count_core_metrics(metrics) < 4:
                        tokens = load_tokens(ocr_pdf_document(pdf_path, cache_key))
                        resolved_year = resolve_report_year(report, tokens, years)
                    if resolved_year is None or resolved_year in collected:
                        continue
                    if tokens:
                        ocr_metrics = extract_metrics(tokens, resolved_year)
                        if count_core_metrics(ocr_metrics) > count_core_metrics(metrics):
                            metrics = ocr_metrics
                    if count_core_metrics(metrics) < 4:
                        pdf_table_metrics = extract_metrics_from_pdf_tables(pdf_path, resolved_year)
                        if count_core_metrics(pdf_table_metrics) > count_core_metrics(metrics):
                            metrics = pdf_table_metrics
                    if count_core_metrics(metrics) < 4:
                        pdf_text_metrics = extract_metrics_from_pdf_text(pdf_path, resolved_year)
                        if count_core_metrics(pdf_text_metrics) > count_core_metrics(metrics):
                            metrics = pdf_text_metrics
                    publication_date = infer_publication_date(report.url)
                    publication_year = report.publication_year or infer_publication_year(report.url)
                    core_metric_count = count_core_metrics(metrics)
                    row = {
                        "emetteur": company.name,
                        "company_url": company.url,
                        "fiscal_year": resolved_year,
                        "report_year": publication_year,
                        "publication_date": publication_date,
                        "report_title": report.title,
                        "report_url": report.url,
                        "status": "ok",
                        "status_reason": None,
                        "diagnostic": None,
                        "core_metrics_count": core_metric_count,
                        **metrics,
                    }
                    if core_metric_count == 0:
                        row["status"] = "parsed_but_empty"
                        row["status_reason"] = "ocr_extracted_no_core_metric"
                        row["diagnostic"] = f"report={report.title}"
                    elif core_metric_count < 4:
                        row["status_reason"] = "partial_core_metrics"
                        row["diagnostic"] = f"core_metrics_count={core_metric_count}; report={report.title}"
                    collected[resolved_year] = row
                    if len(collected) == len(years):
                        break
                except Exception as exc:
                    candidate_year = report.year
                    if candidate_year in years and candidate_year not in collected:
                        collected[candidate_year] = {
                            "emetteur": company.name,
                            "company_url": company.url,
                            "fiscal_year": candidate_year,
                            "report_year": report.publication_year,
                            "publication_date": infer_publication_date(report.url),
                            "report_title": report.title,
                            "report_url": report.url,
                            "status": "report_error",
                            "status_reason": type(exc).__name__,
                            "diagnostic": str(exc),
                            "core_metrics_count": 0,
                        }

            for year in sorted(years):
                if year in collected:
                    rows.append(collected[year])
                    continue
                status_reason, diagnostic = classify_missing_year_reason(reports, year)
                rows.append(
                    {
                        "emetteur": company.name,
                        "company_url": company.url,
                        "fiscal_year": year,
                        "report_year": None,
                        "publication_date": None,
                        "report_title": None,
                        "report_url": None,
                        "status": "missing_report",
                        "status_reason": status_reason,
                        "diagnostic": diagnostic,
                        "core_metrics_count": 0,
                    }
                )

            if company_index % checkpoint_every == 0:
                export_dataframe(finalize_dataframe(merge_rows([], rows)), output_path)

    dataframe = finalize_dataframe(merge_rows([], rows))
    export_dataframe(dataframe, output_path)
    print(f"Wrote {len(dataframe)} rows to {output_path}")
    if not dataframe.empty:
        print("\nStatus summary:")
        print(dataframe["status"].value_counts(dropna=False).to_string())
        if "status_reason" in dataframe.columns:
            reason_counts = dataframe["status_reason"].fillna("ok_or_unclassified").value_counts(dropna=False)
            print("\nReason summary:")
            print(reason_counts.to_string())


if __name__ == "__main__":
    main()
