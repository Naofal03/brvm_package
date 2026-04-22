import pandas as pd
from brvm_package.api.market import list_assets
from brvm_package.fundamentals.core import fundamental_history

def build_equity_excel(filename: str = "brvm_equities.xlsx"):
    symbols = list_assets()
    years = list(range(2018, 2026))
    data = []
    for symbol in symbols:
        hist = fundamental_history(symbol)
        row = {"Symbol": symbol}
        for year in years:
            # Cherche le snapshot le plus proche du 31/12 de chaque année
            snap = hist[hist.index.year == year]
            if not snap.empty:
                snap = snap.iloc[-1]
                row[f"Equity_{year}"] = snap.get("roe")
                row[f"NetIncome_{year}"] = snap.get("net_income")
            else:
                row[f"Equity_{year}"] = None
                row[f"NetIncome_{year}"] = None
        data.append(row)
    # Construction du DataFrame
    columns = ["Symbol"]
    for year in years:
        columns += [f"Equity_{year}", f"NetIncome_{year}"]
    df = pd.DataFrame(data, columns=columns)
    df.to_excel(filename, index=False)
    print(f"Fichier Excel généré: {filename}")

if __name__ == "__main__":
    build_equity_excel()
