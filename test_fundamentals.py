import asyncio
import httpx
from bs4 import BeautifulSoup

async def fetch_sika_societe(symbol):
    url = f"https://www.sikafinance.com/marches/societe/{symbol}"
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        res = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code != 200:
            print(f"Sika returned {res.status_code} for {url}")
            return
        
        soup = BeautifulSoup(res.text, "html.parser")
        print(f"--- SikaFinance ({symbol}) ---")
        
        # Let's find some key tables or labels like "Nombre total de titres", "Capitalisation", "Chiffre d'affaires"
        labels = [
            "Nombre total de titres", "Titre du flottant", 
            "Capitalisation", "Chiffre d'affaires", "Résultat net", "Dividende"
        ]
        text_nodes = soup.find_all(string=True)
        for t in text_nodes:
            tt = t.strip()
            for l in labels:
                if l.lower() in tt.lower():
                    parent = t.parent
                    print(f"Found '{tt}' in <{parent.name}>")
                    # Try to get next sibling or parent's next sibling
                    try:
                        print(f"  Next: {parent.find_next_sibling().text.strip()}")
                    except:
                        pass

async def fetch_rb_mouvements(symbol):
    # The user provided richbourse.com/common/mouvements/index/BICB, let's try net first then com
    url = f"https://www.richbourse.net/common/mouvements/index/{symbol}"
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        res = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code != 200:
            print(f"RichBourse returned {res.status_code} for {url}")
            return
            
        print(f"\n--- RichBourse Mouvements ({symbol}) ---")
        soup = BeautifulSoup(res.text, "html.parser")
        tables = soup.find_all("table")
        print(f"Found {len(tables)} tables")
        if tables:
            # print headers of first table
            headers = [th.text.strip() for th in tables[0].find_all("th")]
            print(f"Table 0 headers: {headers}")
            rows = tables[0].find_all("tr")[1:3]
            for r in rows:
                print([td.text.strip() for td in r.find_all("td")])

async def main():
    await fetch_sika_societe("SNTS.sn")
    await fetch_rb_mouvements("SNTS")

if __name__ == "__main__":
    asyncio.run(main())
