import httpx
import asyncio
from bs4 import BeautifulSoup

async def main():
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        res = await client.get("https://www.sikafinance.com/analyses/conseil/SNTS.sn", headers={"User-Agent": "Mozilla/5.0"})
        print("Analyse length:", len(res.text))
        soup = BeautifulSoup(res.text, "html.parser")
        for tag in soup.find_all(string=lambda t: "PBR" in str(t) or "Capitaux" in str(t)):
            print(f"FOUND in Analyse: {tag.strip()}")

if __name__ == "__main__":
    asyncio.run(main())
