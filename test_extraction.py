import asyncio
import httpx
from bs4 import BeautifulSoup
import re
import json

async def scrape_new_snts():
    ticker = "SNTS"
    url = f"https://www.sikafinance.com/marches/cotation_{ticker}.sn"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9",
        "Referer": "https://www.sikafinance.com/"
    }
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Essayer de trouver simplement les tables de ratios ou informations clés
            tables = soup.find_all("table")
            print(f"Trouvé {len(tables)} tables HTML classiques.")
            
            for t in tables[:1]: # test sur la première
                for tr in t.find_all("tr")[:5]: # test sur les premières lignes
                    cells = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                    print(" | ".join(cells))
            
            # Chercher dans un éventuel JSON imbriqué (window.__INITIAL_STATE__ ou autre)
            scripts = soup.find_all("script")
            for s in scripts:
                if s.string and "Rendement" in s.string or "PER" in s.string or "api/general/GetHistos" in s.string:
                    print("Trouvé script pertinent:")
                    print(s.string[:300])
                    
            # API endpoint
            api_test = await client.post(
                "https://www.sikafinance.com/api/general/GetHistos", 
                json={"ticker": "SNTS.sn", "datedeb": "2026-01-01", "datefin": "2026-04-15", "xperiod": "0"},
                headers=headers
            )
            print(f"API Histos Test Status: {api_test.status_code}")
            if api_test.status_code == 200:
                 print(api_test.text[:200])

if __name__ == "__main__":
    asyncio.run(scrape_new_snts())
