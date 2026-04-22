"""
Scraper for BRVM listed companies' financial report PDF links.
"""

class BRVMReportScraper:
    import requests
    from bs4 import BeautifulSoup
    import re

    BASE_URL = "https://www.brvm.org/fr/cours-actions"
    REPORTS_URL = "https://www.brvm.org/fr/rapports-societes-cotees"

    def list_companies(self):
        """Scrape the list of companies and their codes from BRVM."""
        import certifi
        resp = self.requests.get(self.BASE_URL, verify=certifi.where())
        soup = self.BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")
        companies = []
        if table:
            for row in table.find_all("tr")[1:]:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    code = cols[0].get_text(strip=True)
                    name = cols[1].get_text(strip=True)
                    companies.append({"code": code, "name": name})
        return companies

    def get_report_links(self, company_code, years):
        """Return a dict {year: pdf_url} for the given company and years (2020–2025)."""
        import certifi
        # Go to the reports page, find the row for the company, then extract PDF links for each year
        resp = self.requests.get(self.REPORTS_URL, verify=certifi.where())
        soup = self.BeautifulSoup(resp.text, "html.parser")
        links_by_year = {}
        # Find the table with reports
        table = soup.find("table")
        if not table:
            return links_by_year
        for row in table.find_all("tr")[1:]:
            cols = row.find_all("td")
            if len(cols) < 2:
                continue
            code = cols[0].get_text(strip=True)
            if code != company_code:
                continue
            # Find all links in the row
            for link in row.find_all("a", href=True):
                href = link["href"]
                text = link.get_text()
                # Try to extract year from link text or href
                year_match = self.re.search(r"20[0-9]{2}", text + href)
                if year_match:
                    year = int(year_match.group())
                    if year in years:
                        links_by_year[year] = href if href.startswith("http") else f"https://www.brvm.org{href}"
        return links_by_year
