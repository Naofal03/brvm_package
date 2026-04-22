import re
import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
from datetime import datetime, timedelta, date

from brvm_package.data.catalog import get_sika_ticker

logger = logging.getLogger(__name__)

class SikaFinanceClient:
    """Client asynchrone pour extraire les données depuis SikaFinance.com"""
    BASE_URL = "https://www.sikafinance.com"

    def _resolve_ticker(self, symbol: str) -> str:
        """Ajoute le bon suffixe pays requis par le nouveau site SikaFinance."""
        return get_sika_ticker(symbol)

    def _normalize_date(self, value: str | date) -> date:
        if isinstance(value, date):
            return value
        return datetime.strptime(value, "%Y-%m-%d").date()

    def _clean_number(self, value: str | None, multiplier: float = 1.0) -> float | None:
        if value is None:
            return None
        cleaned = (
            str(value)
            .replace("\xa0", " ")
            .replace("FCFA", "")
            .replace("XOF", "")
            .replace("MFCFA", "")
            .replace("MXOF", "")
            .replace("%", "")
            .replace(" ", "")
            .replace(",", ".")
            .strip()
        )
        if cleaned in {"", "-", "--"}:
            return None
        try:
            return float(cleaned) * multiplier
        except ValueError:
            return None

    def _extract_number(self, text: str, patterns: list[tuple[str, float]]) -> float | None:
        for pattern, multiplier in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
            if match:
                value = self._clean_number(match.group(1), multiplier=multiplier)
                if value is not None:
                    return value
        return None

    def _extract_text(self, text: str, patterns: list[str]) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
            if match:
                value = re.sub(r"\s+", " ", match.group(1)).strip()
                if value:
                    return value
        return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_historical_data(
        self,
        symbol: str,
        start_date: str | date,
        end_date: str | date,
        period: int = 0,
    ) -> list[dict]:
        """
        Récupère l'historique via l'API JSON avec pagination pour contourner l'erreur 'toolong'.
        """
        api_url = f"{self.BASE_URL}/api/general/GetHistos"
        resolved_ticker = self._resolve_ticker(symbol)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Origin": self.BASE_URL,
            "Referer": f"{self.BASE_URL}/marches/cotation_{resolved_ticker}"
        }
        
        all_data = []
        start_dt = self._normalize_date(start_date)
        end_dt = self._normalize_date(end_date)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            current_start = start_dt
            while current_start <= end_dt:
                # Bloc de 60 jours maximum pour éviter l'erreur 'toolong'
                current_end = min(current_start + timedelta(days=60), end_dt)
                
                payload = {
                    "ticker": resolved_ticker,
                    "datedeb": current_start.strftime("%Y-%m-%d"),
                    "datefin": current_end.strftime("%Y-%m-%d"),
                    "xperiod": str(period)
                }

                response = await client.post(api_url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                if "lst" in data and isinstance(data["lst"], list):
                    all_data.extend(data["lst"])
                elif data.get("error") == "toolong":
                    logger.warning(f"Bloc trop long pour {resolved_ticker} ({current_start} à {current_end}).")
                
                current_start = current_end + timedelta(days=1)
                
        # Dédoublonnage sécurisé sur la clé "Date"
        seen = set()
        clean_data = []
        for row in all_data:
            d = row.get("Date")
            if d and d not in seen:
                clean_data.append(row)
                seen.add(d)
                
        # Tri chronologique ascendant : l'API renvoie des formats DD/MM/YYYY
        try:
            clean_data.sort(key=lambda x: datetime.strptime(x["Date"], "%d/%m/%Y"))
        except Exception:
            pass # On laisse tel quel si le format varie
            
        return clean_data

    async def close(self) -> None:
        """Méthode de compatibilité (le client HTTP est géré par contexte)."""
        return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _fetch_page(self, endpoint: str) -> str:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                "Referer": "https://www.sikafinance.com/"
            }
            url = f"{self.BASE_URL}{endpoint}"
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text

    def _extract_fundamental(self, soup: BeautifulSoup, label: str) -> str | None:
        element = soup.find(string=re.compile(label, re.IGNORECASE))
        if element:
            parent = element.parent
            if parent and parent.find_next_sibling():
                return parent.find_next_sibling().text.strip()
        return None

    async def get_ticker_info(self, symbol: str) -> dict:
        """Récupère les infos Fondamentales depuis la page société de SikaFinance."""
        resolved_ticker = self._resolve_ticker(symbol)
        
        # La page societe contient un tableau financier des 5 dernières années
        try:
            html = await self._fetch_page(f"/marches/societe/{resolved_ticker}")
            soup = BeautifulSoup(html, "html.parser")
            
            fundamentals = {
                "source": "SikaFinance",
                "symbol": symbol.upper(),
                "resolved_ticker": resolved_ticker,
                "revenue": None,
                "net_income": None,
                "eps": None,
                "per": None,
                "dividend": None,
                "pbr": None,
                "roe": None,
                "market_cap": None,
                "shares_outstanding": None,
                "float_ratio": None,
                "beta_1y": None,
                "major_shareholders": None,
            }

            society_text = soup.get_text("\n", strip=True)
            fundamentals["shares_outstanding"] = self._extract_number(
                society_text,
                [(r"Nombre de titres\s*:?\s*([0-9\s\xa0]+)", 1.0)],
            )
            fundamentals["float_ratio"] = self._extract_number(
                society_text,
                [(r"Flottant\s*:?\s*([0-9\s\xa0,]+)", 1.0)],
            )
            fundamentals["market_cap"] = self._extract_number(
                society_text,
                [(r"Valorisation de la société\s*:?\s*([0-9\s\xa0,]+)\s*MFCFA", 1_000_000.0)],
            )
            fundamentals["major_shareholders"] = self._extract_text(
                society_text,
                [r"Principaux actionnaires\s*(.+?)\s*Les chiffres sont en millions de FCFA"],
            )
            
            tables = soup.find_all("table")
            if len(tables) > 1:
                # La table 1 contient les fondamentaux
                table = tables[1]
                
                # Helper pour nettoyer les nombres (ex: "5 708" ou "46,76%")
                def clean_num(val_str: str) -> float | None:
                    if not val_str or val_str == "-" or val_str.isspace():
                        return None
                    clean_str = val_str.replace('\xa0', '').replace(' ', '').replace('%', '').replace(',', '.').strip()
                    try:
                        return float(clean_str)
                    except ValueError:
                        return None

                for tr in table.find_all("tr"):
                    cols = [td.get_text(strip=True).replace('\xa0', ' ') for td in tr.find_all(["td", "th"])]
                    if not cols or len(cols) < 2:
                        continue
                    
                    label = cols[0].lower()
                    
                    # On prend toujours la dernière colonne disponible avec une donnée
                    last_val = None
                    for col in reversed(cols[1:]):
                        if col and col != "-" and not col.isspace():
                            last_val = col
                            break
                            
                    if not last_val:
                        continue
                        
                    parsed_val = clean_num(last_val)
                    if not parsed_val:
                        continue
                        
                    if "chiffre d'affaires" in label:
                        # Les chiffres de SikaFinance sont en millions de FCFA (habituellement pour CA et RN)
                        # Pour CA, s'assurer que c'est un float
                        fundamentals["revenue"] = parsed_val * 1_000_000
                    elif "résultat net" in label or "resultat net" in label:
                        fundamentals["net_income"] = parsed_val * 1_000_000
                    elif "bnpa" in label:
                        fundamentals["eps"] = parsed_val
                    elif "per" in label:
                        fundamentals["per"] = parsed_val
                    elif "dividende" in label and "croissance" not in label:
                        fundamentals["dividend"] = parsed_val

            try:
                quote_html = await self._fetch_page(f"/marches/cotation_{resolved_ticker}")
                quote_text = BeautifulSoup(quote_html, "html.parser").get_text("\n", strip=True)
                fundamentals["beta_1y"] = self._extract_number(
                    quote_text,
                    [(r"Beta\s*1\s*an\s*\|?\s*([0-9\s\xa0,]+)", 1.0)],
                )
                if fundamentals["market_cap"] is None:
                    fundamentals["market_cap"] = self._extract_number(
                        quote_text,
                        [(r"Valorisation\s*\|?\s*([0-9\s\xa0,]+)\s*M[X]?[A-Z]*OF", 1_000_000.0)],
                    )
                if fundamentals["pbr"] is None:
                    fundamentals["pbr"] = self._extract_number(
                        quote_text,
                        [(r"\bPBR\b\s*\|?\s*([0-9\s\xa0,]+)", 1.0)],
                    )
                if fundamentals["roe"] is None:
                    fundamentals["roe"] = self._extract_number(
                        quote_text,
                        [(r"\bROE\b\s*\|?\s*([0-9\s\xa0,]+)", 1.0)],
                    )
            except Exception:
                logger.debug("Aucun enrichissement cotation SikaFinance pour %s.", symbol.upper())
                        
            return fundamentals
            
        except Exception as e:
            logger.error(f"Erreur extraction fondamentaux SikaFinance ({symbol}): {e}")
            return {}
