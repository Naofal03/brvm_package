"""
Parser for extracting financial metrics from tables/text.
"""

class FinancialReportParser:
    def parse(self, tables_or_text):
        """
        Parse extracted tables (list of DataFrame) or OCR text (list of str) and return a dict of financial metrics.
        Gère les intitulés en français typiques des états financiers BRVM.
        """
        import re
        import pandas as pd
        # Champs à extraire (français)
        fields = {
            "revenue": ["chiffre d'affaires", "ca"],
            "operating_income": ["résultat opérationnel"],
            "net_income": ["résultat net"],
            "equity": ["capitaux propres"],
            "total_assets": ["total actif"],
            "total_liabilities": ["dettes totales", "total dettes"],
            "current_assets": ["actifs courants"],
            "current_liabilities": ["passifs courants"],
            "operating_margin": ["marge opérationnelle"],
            "net_margin": ["marge nette"],
            "roe": ["roe", "return on equity"],
            "roa": ["roa", "return on assets"],
            "debt_ratio": ["ratio d'endettement"],
            "equity_ratio": ["autonomie financière"],
            "current_ratio": ["ratio de liquidité générale"],
        }
        result = {k: None for k in fields}
        # Si tables (DataFrame)
        if isinstance(tables_or_text, list) and tables_or_text and hasattr(tables_or_text[0], 'columns'):
            for df in tables_or_text:
                for row in df.values:
                    row_str = ' '.join(str(x).lower() for x in row)
                    for key, patterns in fields.items():
                        for pat in patterns:
                            if pat in row_str:
                                # Cherche un nombre dans la ligne
                                match = re.search(r"([\d\s.,]+)", row_str)
                                if match:
                                    val = match.group(1).replace(' ', '').replace(',', '.').replace('\xa0', '')
                                    try:
                                        result[key] = float(val)
                                    except Exception:
                                        pass
        # Si texte OCR
        elif isinstance(tables_or_text, list) and tables_or_text and isinstance(tables_or_text[0], str):
            for page in tables_or_text:
                lines = page.lower().split('\n')
                for line in lines:
                    for key, patterns in fields.items():
                        for pat in patterns:
                            if pat in line:
                                match = re.search(r"([\d\s.,]+)", line)
                                if match:
                                    val = match.group(1).replace(' ', '').replace(',', '.').replace('\xa0', '')
                                    try:
                                        result[key] = float(val)
                                    except Exception:
                                        pass
        return result
