"""
Parser for extracting financial metrics from tables/text.
Enhanced: table-priority, French patterns, auto-ratios (ROE=net/equity).
"""


class FinancialReportParser:
    def parse(self, tables_or_text):
        """
        Parse tables/OCR → metrics dict.
        Priority: camelot tables → column/row search.
        Fallback: OCR.
        Auto-compute ratios.
        """
        import re
        import pandas as pd
        import numpy as np

        FIELDS = {
"revenue": ["chiffre d.?affaires?", "chiffre d affaires", "ventes", "produits d.?exploitation", "total produit", "total produits"],
            "operating_income": ["résultat opérationnel", "résultat d.?exploitation", "ebit"],
            "net_income": ["résultat net", "bénéfice net", "perte net"],
            "equity": ["capitaux propres", "capitaux", "fonds propres"],
            "total_assets": ["total actif", "actif total", "bilan"],
            "total_liabilities": ["dettes totales", "passif total", "total passif"],
            "current_assets": ["actifs courants", "actif courant"],
            "current_liabilities": ["passifs courants", "passif courant", "dettes à court terme"],
        }
        RATIOS = {
            "operating_margin": ("operating_income", "revenue"),
            "net_margin": ("net_income", "revenue"),
            "roe": ("net_income", "equity"),
            "roa": ("net_income", "total_assets"),
            "debt_ratio": ("total_liabilities", "total_assets"),
            "equity_ratio": ("equity", "total_assets"),
            "current_ratio": ("current_assets", "current_liabilities"),
        }

        result = {**{k: None for k in FIELDS}, **{k: None for k in RATIOS}}

        def normalize_label(text: str) -> str:
            text = text.lower().replace("\xa0", " ")
            text = (
                text.replace("é", "e")
                .replace("è", "e")
                .replace("ê", "e")
                .replace("à", "a")
                .replace("ù", "u")
                .replace("ô", "o")
            )
            text = re.sub(r"[^a-z0-9]+", " ", text)
            return re.sub(r"\s+", " ", text).strip()

        def normalize_num(text: str) -> float | None:
            cleaned = str(text).replace("\xa0", " ").strip()
            matches = re.findall(r"-?\d[\d\s.,]*", cleaned)
            if not matches:
                return None
            candidate = max(matches, key=lambda item: sum(ch.isdigit() for ch in item))
            candidate = candidate.replace(" ", "")
            if "," in candidate and "." not in candidate:
                candidate = candidate.replace(",", ".")
            elif "," in candidate and "." in candidate:
                candidate = candidate.replace(",", "")
            candidate = re.sub(r"[^0-9.\-]", "", candidate)
            if candidate in {"", "-", ".", "-."}:
                return None
            return float(candidate)

        def find_field(text: str, patterns: list) -> float | None:
            lower = normalize_label(text)
            for pat in patterns:
                normalized_pattern = normalize_label(pat)
                match = re.search(rf"{normalized_pattern}\s*:?\s*([\d\s.,-]+)", lower, re.I)
                if match:
                    return normalize_num(match.group(1))
            return None

        # Tables first
        if isinstance(tables_or_text, list):
            for item in tables_or_text:
                dataframe = None
                if isinstance(item, pd.DataFrame):
                    dataframe = item
                elif hasattr(item, 'df') and isinstance(item.df, pd.DataFrame):
                    dataframe = item.df

                if dataframe is not None:
                    df_lower = dataframe.fillna('').astype(str).apply(lambda s: s.str.lower())
                    for col in df_lower.columns:
                        col_text = ' '.join(df_lower[col].dropna())
                        for field, pats in FIELDS.items():
                            val = find_field(col_text, pats)
                            if val is not None:
                                result[field] = val
                    for _, row in dataframe.iterrows():
                        row_values = [str(value).strip() for value in row.dropna().tolist() if str(value).strip()]
                        if len(row_values) >= 2:
                            label_text = row_values[0]
                            value_text = " ".join(row_values[1:])
                            normalized_label_text = normalize_label(label_text)
                            for field, pats in FIELDS.items():
                                if any(normalize_label(pat) in normalized_label_text for pat in pats):
                                    val = normalize_num(value_text)
                                    if val is not None:
                                        result[field] = val
                                        break

                        row_text = ' '.join(row_values)
                        for field, pats in FIELDS.items():
                            val = find_field(row_text, pats)
                            if val is not None:
                                result[field] = val
                                break
                elif isinstance(item, str):
                    for field, pats in FIELDS.items():
                        val = find_field(item, pats)
                        if val:
                            result[field] = val

        # Ratios
        for ratio, (num_f, den_f) in RATIOS.items():
            n, d = result.get(num_f), result.get(den_f)
            if n is not None and d and d != 0:
                result[ratio] = n / d

        # Clean
        for k in result:
            v = result[k]
            if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                result[k] = None

        return result
