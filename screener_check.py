import httpx
import asyncio
from bs4 import BeautifulSoup

async def main():
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        # Check an overview / screener page
        res = await client.get("https://www.sikafinance.com/marches/evolution", headers={"User-Agent": "Mozilla/5.0"})
        print("Evolution length:", len(res.text))
        soup = BeautifulSoup(res.text, "html.parser")
        print("Text preview:", soup.get_text()[:500].replace('\n', ' '))
        # Check PBR references
        print("PBR matches:", len(soup.find_all(string=lambda t: "PBR" in str(t))))

        res = await client.get("https://www.sikafinance.com/marches/comparateur", headers={"User-Agent": "Mozilla/5.0"})
        print("Comparateur length:", len(res.text))
        # let's grep lines
        for line in res.text.split('\n'):
            if 'PBR' in line or 'pbr' in line.lower() or 'capitaux' in line.lower():
                print(line.strip()[:100])

if __name__ == "__main__":
    asyncio.run(main())
