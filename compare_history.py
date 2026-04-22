import asyncio
import time
from brvm_package.scraper.sikafinance import SikaFinanceClient
from brvm_package.scraper.richbourse import RichbourseClient

async def compare_sources():
    sika = SikaFinanceClient()
    rich = RichbourseClient()
    symbol = "SNTS"
    
    print(f"Comparaison de l'Historique Quotidien pour {symbol}...")
    
    # 1. Test SikaFinance
    start_sika = time.perf_counter()
    # On prend une période de 3 mois et demi
    data_sika = await sika.get_historical_data(symbol, "2025-12-01", "2026-04-15", period=0)
    time_sika = time.perf_counter() - start_sika
    
    # 2. Test Richbourse
    start_rich = time.perf_counter()
    data_rich = await rich.get_historical_prices(symbol)
    time_rich = time.perf_counter() - start_rich
    
    print("\n--- RÉSULTATS SIKAFINANCE ---")
    print(f"Temps d'exécution : {time_sika:.4f} secondes")
    print(f"Nombre d'enregistrements : {len(data_sika)}")
    if data_sika:
        # Formater un échantillon
        sample_sika = [d for d in data_sika if d['Date'] == '15/04/2026']
        if not sample_sika and len(data_sika) > 0: sample_sika = [data_sika[-1]]
        print(f"Échantillon (15/04/2026 ou dernier) : {sample_sika[0]}")
        
    print("\n--- RÉSULTATS RICHBOURSE ---")
    print(f"Temps d'exécution : {time_rich:.4f} secondes")
    print(f"Nombre d'enregistrements : {len(data_rich)}")
    if data_rich:
        # Formater un échantillon. RichBourse a le format "15/04/2026"
        sample_rich = [d for d in data_rich if d['date'] == '15/04/2026']
        if not sample_rich and len(data_rich) > 0: sample_rich = [data_rich[0]]
        print(f"Échantillon (15/04/2026 ou premier) : {sample_rich[0]}")

if __name__ == "__main__":
    asyncio.run(compare_sources())
