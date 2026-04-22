import pandas as pd
from pathlib import Path

def financials_all() -> pd.DataFrame:
    '''
    Retourne les données financières BRVM 2020-2025 (tous stocks).
    Colonnes : emetteur, report_year, resultat_operationnel, resultat_net, chiffre_affaires, capitaux_propres,
    total_actif, dettes_totales, actifs_courants, passifs_courants, marge_operationnelle, marge_nette,
    ROE, ROA, ratio_endettement, autonomie_financiere, ratio_liquidite_generale, etc.
    '''
    csv_path = Path(__file__).parent.parent.parent / 'data' / 'brvm_financials_2020_2025.csv'
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        df = df.sort_values(['emetteur', 'report_year'])
        return df
    raise FileNotFoundError(f'CSV non trouvé: {csv_path}. Lancez "python scripts/extract_brvm_financials.py"')
