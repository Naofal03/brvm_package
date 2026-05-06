from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from brvm_package.data.catalog import get_asset_catalog

BASE_URL = "https://www.brvm.org"
LISTING_URL = f"{BASE_URL}/fr/rapports-societes-cotees"
USER_AGENT = "Mozilla/5.0 (compatible; brvm-package/0.2; +https://github.com/naofal/brvm-package)"


@dataclass(slots=True)
class _CandidateReport:
    title: str
    url: str
    fiscal_year: int | None
    score: int


def _normalize_text(value: str) -> str:
    text = value.replace("\u2019", "'").replace("\xa0", " ").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _infer_fiscal_year(title: str, url: str) -> int | None:
    normalized_title = _normalize_text(title)
    normalized_url = _normalize_text(url.replace("_", " ").replace("-", " "))

    patterns = (
        r"exercice\s+(20\d{2})",
        r"au\s+31\s+decembre\s+(20\d{2})",
        r"etats?\s+financiers?.*?(20\d{2})",
        r"comptes?.*?(20\d{2})",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized_title)
        if match:
            return int(match.group(1))

    title_years = [int(year) for year in re.findall(r"\b(20\d{2})\b", normalized_title)]
    if title_years:
        return max(title_years)

    url_years = [int(year) for year in re.findall(r"\b(20\d{2})\b", normalized_url)]
    if not url_years:
        return None
    publication_year = min(url_years)
    return publication_year - 1 if publication_year >= 2001 else publication_year


def _report_score(title: str, target_year: int) -> int:
    normalized = _normalize_text(title)
    score = 0
    if "etat financier" in normalized or "etats financiers" in normalized:
        score += 120
    if str(target_year) in normalized:
        score += 60
    if "approuve" in normalized or "annuel" in normalized or "systeme normal" in normalized:
        score += 35
    if "provisoire" in normalized:
        score += 10
    if "rapport des commissaires" in normalized or "rapport des cacs" in normalized or "cac" in normalized:
        score -= 120
    if "rapport" in normalized and "etat financier" not in normalized and "etats financiers" not in normalized:
        score -= 40
    if "trimestriel" in normalized or "semestriel" in normalized or "semestre" in normalized:
        score -= 60
    return score


class BRVMReportScraper:
    def __init__(self, timeout: float = 60.0) -> None:
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def list_companies(self) -> list[dict[str, str]]:
        catalog = get_asset_catalog()
        return [
            {"code": code, "name": metadata["name"]}
            for code, metadata in sorted(catalog.items(), key=lambda item: item[0])
        ]

    async def fetch_reports_page(self) -> str:
        client = await self._get_client()
        response = await client.get(LISTING_URL)
        response.raise_for_status()
        return response.text

    async def fetch_company_page(self, company_url: str) -> str:
        client = await self._get_client()
        response = await client.get(f"{company_url}?field_type_rapport_tid=57")
        response.raise_for_status()
        return response.text

    def extract_company_links(self, html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        catalog = get_asset_catalog()
        name_to_code = {_normalize_text(meta["name"]): code for code, meta in catalog.items()}
        links: dict[str, str] = {}

        for anchor in soup.select("a[href^='/fr/rapports-societe-cotes/']"):
            href = anchor.get("href", "").strip()
            name = anchor.get_text(" ", strip=True)
            if not href or not name:
                continue

            normalized_name = _normalize_text(name)
            matched_code = name_to_code.get(normalized_name)
            if matched_code is None:
                for catalog_name, code in name_to_code.items():
                    if normalized_name in catalog_name or catalog_name in normalized_name:
                        matched_code = code
                        break
            if matched_code is None:
                continue

            links[matched_code] = urljoin(BASE_URL, href)

        return links

    def extract_financial_links(self, html: str, years: list[int]) -> dict[int, str]:
        soup = BeautifulSoup(html, "html.parser")
        best_by_year: dict[int, _CandidateReport] = {}

        for row in soup.select("div.view-content table tbody tr"):
            title_node = row.find("strong")
            link_node = row.find("a", href=True)
            if title_node is None or link_node is None:
                continue

            title = title_node.get_text(" ", strip=True)
            url = urljoin(BASE_URL, link_node["href"])
            fiscal_year = _infer_fiscal_year(title, url)
            if fiscal_year not in years:
                continue

            score = _report_score(title, fiscal_year)
            if score < 40:
                continue

            candidate = _CandidateReport(title=title, url=url, fiscal_year=fiscal_year, score=score)
            current = best_by_year.get(fiscal_year)
            if current is None or candidate.score > current.score:
                best_by_year[fiscal_year] = candidate

        return {year: candidate.url for year, candidate in best_by_year.items()}

    async def download_file(self, url: str, destination: Path) -> dict[str, str | bool]:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            return {"cached": True, "dest": str(destination)}

        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()
        destination.write_bytes(response.content)
        return {"cached": False, "dest": str(destination), "url": url}
