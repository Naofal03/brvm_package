import asyncio
import time
from datetime import date, timedelta
from src.brvm_package.scraper.sikafinance import SikaFinanceClient, SIKA_TICKER_MAP
from rich.console import Console
from rich.table import Table
import httpx

console = Console()

async def fetch_sika(client, symbol, start, end):
    t0 = time.time()
    try:
        data = await client.get_historical_data(symbol, start_date=start, end_date=end)
        return data, time.time() - t0
    except Exception as e:
        console.print(f"Error Sika {symbol}: {e}")
        return None, time.time() - t0

async def fetch_rb(symbol):
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as htclient:
            url = f"https://www.richbourse.net/cotation/{symbol.upper()}/historique"
            res = await htclient.get(url, headers={"User-Agent": "Mozilla/5.0"})
            res.raise_for_status()
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(res.text, "html.parser")
            results = []
            table = soup.find("table")
            if table:
                rows = table.find_all("tr")[1:]
                for row in rows:
                    cols = row.find_all(["td", "th"])
                    if len(cols) >= 5:
                        results.append({
                            "date": cols[0].text.strip(),
                            "close": cols[4].text.replace(" ", "").strip()
                        })
            return results, time.time() - t0
    except Exception as e:
        return None, time.time() - t0

def normalize_sika(data):
    res = {}
    if not data: return res
    for r in data:
        if 'Date' in r and 'Close' in r:
            res[r['Date']] = float(r['Close'])
    return res

def normalize_rb(data):
    res = {}
    if not data: return res
    for r in data:
        if 'date' in r and 'close' in r:
            try:
                d_str = r['date']
                if '-' in d_str:
                    d = date.fromisoformat(d_str).strftime("%d/%m/%Y")
                else:
                    d = d_str
                    
                c = float(r['close'].replace(' ', '').replace(',', '.'))
                res[d] = c
            except Exception:
                pass
    return res

async def main():
    sika_c = SikaFinanceClient()
    
    tickers_to_test = list(SIKA_TICKER_MAP.keys())[:5] 
    console.print(f"[cyan]Début du benchmark sur {len(tickers_to_test)} actions...[/cyan]")
    
    end = date.today()
    start = end - timedelta(days=60)
    
    table = Table("Ticker", "Temps Sika", "Temps RB", "Points Sika", "Points RB", "Taux Correspondance Close")
    
    for sym in tickers_to_test:
        sika_data, t_sika = await fetch_sika(sika_c, sym, start, end)
        rb_data, t_rb = await fetch_rb(sym)
        
        s_norm = normalize_sika(sika_data)
        r_norm = normalize_rb(rb_data)
        
        r_norm_filtered = {k:v for k,v in r_norm.items() if k in s_norm}
                
        common_dates = set(s_norm.keys()).intersection(set(r_norm_filtered.keys()))
        
        matches = 0
        if common_dates:
            for d in common_dates:
                if abs(s_norm[d] - r_norm_filtered[d]) < 1.0:
                    matches += 1
            match_rate = (matches / len(common_dates)) * 100
        else:
            match_rate = 0.0
            
        table.add_row(
            sym,
            f"{t_sika:.2f}s",
            f"{t_rb:.2f}s",
            str(len(s_norm)),
            str(len(r_norm)),
            f"{match_rate:.1f}%" if common_dates else "N/A"
        )
        
    console.print(table)

if __name__ == "__main__":
    asyncio.run(main())
