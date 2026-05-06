"""
Pipeline complet asynchrone pour collecter et stocker les états financiers BRVM (2020–2025).
Utilise le nouveau scraper async + ingestion SQLite propre.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from brvm_package.financial_reports.scraper import BRVMReportScraper
from brvm_package.financial_reports.pdf_extractor import FinancialPDFExtractor
from brvm_package.financial_reports.parser import FinancialReportParser
from brvm_package.financial_reports.ingest import ingest_financial_data

logger = logging.getLogger(__name__)

DEFAULT_YEARS = list(range(2020, 2026))


async def collect_all(
    years: list[int] | None = None,
    pdf_dir: str = "pdf_reports",
    max_concurrency: int = 3,
) -> dict[str, Any]:
    """
    Collecte tous les rapports financiers BRVM pour les années demandées.
    Retourne un rapport de collecte avec les succès et erreurs.
    """
    target_years = years if years is not None else DEFAULT_YEARS
    pdf_path = Path(pdf_dir)
    pdf_path.mkdir(parents=True, exist_ok=True)

    scraper = BRVMReportScraper()
    extractor = FinancialPDFExtractor()
    parser = FinancialReportParser()

    companies = scraper.list_companies()
    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def process_company(company: dict[str, str]) -> dict[str, Any]:
        code = company["code"]
        name = company.get("name", code)
        result: dict[str, Any] = {
            "code": code,
            "name": name,
            "years": {},
            "errors": [],
        }

        try:
            # Récupérer la page de la société et extraire les liens financiers
            # Si pas de lien direct, on tente via le catalogue BRVM
            async with semaphore:
                reports_html = await scraper.fetch_reports_page()
                company_links = scraper.extract_company_links(reports_html)

                company_url = company_links.get(code)
                if not company_url:
                    result["errors"].append(f"No company page link found for {code}")
                    return result

                company_html = await scraper.fetch_company_page(company_url)
                financial_links = scraper.extract_financial_links(company_html, years=target_years)

            for year, url in financial_links.items():
                pdf_file = pdf_path / f"{code}_{year}.pdf"
                year_result: dict[str, Any] = {"url": url, "pdf_path": str(pdf_file)}

                try:
                    if not pdf_file.exists():
                        download_info = await scraper.download_file(url, pdf_file)
                        year_result["download"] = download_info
                    else:
                        year_result["download"] = {"cached": True, "dest": str(pdf_file)}

                    tables_or_text = extractor.extract_tables(str(pdf_file))
                    data = parser.parse(tables_or_text)

                    ingest_financial_data(code, year, data)
                    year_result["data"] = data
                    year_result["status"] = "ok"
                except Exception as exc:  # noqa: BLE001
                    year_result["status"] = f"error: {exc}"
                    result["errors"].append(f"{year}: {exc}")

                result["years"][year] = year_result

        except Exception as exc:  # noqa: BLE001
            result["errors"].append(f"global: {exc}")

        return result

    tasks = [process_company(company) for company in companies]
    results = await asyncio.gather(*tasks)

    summary = {
        "companies_total": len(companies),
        "companies_processed": len([r for r in results if not r["errors"]]),
        "companies_with_errors": len([r for r in results if r["errors"]]),
        "details": results,
    }

    logger.info("Collect pipeline finished: %d/%d OK", summary["companies_processed"], summary["companies_total"])
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    report = asyncio.run(collect_all())
    print(report)
