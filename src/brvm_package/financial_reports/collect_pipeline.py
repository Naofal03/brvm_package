
"""
Pipeline complet pour collecter et stocker les états financiers BRVM (2020–2025) pour toutes les sociétés.
"""

# Force l'utilisation du bundle certifi pour HTTPS
import certifi, os
os.environ['SSL_CERT_FILE'] = certifi.where()

from brvm_package.financial_reports.scraper import BRVMReportScraper
from brvm_package.financial_reports.pdf_extractor import FinancialPDFExtractor
from brvm_package.financial_reports.parser import FinancialReportParser
from brvm_package.financial_reports.ingest import ingest_financial_data
import os
import requests

def download_pdf(url, dest):
    resp = requests.get(url)
    resp.raise_for_status()
    with open(dest, 'wb') as f:
        f.write(resp.content)


def collect_all(years=[2020,2021,2022,2023,2024,2025], pdf_dir="pdf_reports"):
    os.makedirs(pdf_dir, exist_ok=True)
    scraper = BRVMReportScraper()
    extractor = FinancialPDFExtractor()
    parser = FinancialReportParser()
    companies = scraper.list_companies()
    for company in companies:
        code = company['code']
        name = company['name']
        print(f"\n--- {code} | {name} ---")
        links = scraper.get_report_links(code, years)
        for year, url in links.items():
            print(f"  {year}: {url}")
            pdf_path = os.path.join(pdf_dir, f"{code}_{year}.pdf")
            if not os.path.exists(pdf_path):
                try:
                    download_pdf(url, pdf_path)
                except Exception as e:
                    print(f"    Erreur téléchargement: {e}")
                    continue
            try:
                tables_or_text = extractor.extract_tables(pdf_path)
                data = parser.parse(tables_or_text)
                ingest_financial_data(code, year, data)
                print(f"    Données extraites et stockées: {data}")
            except Exception as e:
                print(f"    Erreur extraction/parsing/ingest: {e}")

if __name__ == "__main__":
    collect_all()
