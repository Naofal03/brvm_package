import re
import logging
from bs4 import BeautifulSoup
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class RichbourseClient:
    """Client asynchrone pour extraire les données depuis RichBourse."""
    BASE_URL = "https://www.richbourse.com"
    MARKET_QUOTES_PATH = "/common/variation/index/veille/tout"
    HISTORY_PATH_TEMPLATE = "/common/variation/historique/{symbol}"

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            http2=True,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/135.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Upgrade-Insecure-Requests": "1",
            }
        )

    async def close(self):
        await self.client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
    async def get_market_quotes(self) -> list[dict]:
        """Récupère les cotations générales consolidées du marché."""
        url = f"{self.BASE_URL}{self.MARKET_QUOTES_PATH}"
        response = await self.client.get(url)
        if response.status_code in {403, 404}:
            logger.warning(
                "RichBourse a refuse l'acces aux cotations consolidees (%s pour %s).",
                response.status_code,
                url,
            )
            return []
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        tables = soup.find_all("table")
        if not tables:
            logger.warning("RichBourse n'expose pas de table de cotations exploitable sur %s.", url)
            return results

        main_table = max(tables, key=lambda t: len(t.find_all("tr")))
        headers = [self._normalize_header(cell.get_text(" ", strip=True)) for cell in main_table.find_all("th")]
        for row in main_table.find_all("tr")[1:]:
            cols = row.find_all("td")
            if not cols:
                continue

            values = [col.get_text(" ", strip=True) for col in cols]
            row_map = {headers[i] if i < len(headers) else f"col_{i}": values[i] for i in range(len(values))}

            symbol = self._first_match(row_map, ("symbole", "symbol"))
            if not symbol or symbol.upper() == "TOTAL":
                continue

            results.append({
                "symbol": symbol,
                "price": self._first_match(row_map, ("coursactuel", "cours", "close", "dernier")),
                "variation": self._first_match(row_map, ("variation",)),
                "volume": self._first_match(row_map, ("volume",)),
                "value_traded": self._first_match(row_map, ("valeurfcfa", "valeur")),
            })
        return results

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
    async def get_historical_prices(self, symbol: str) -> list[dict]:
        """Récupère l'historique quotidien depuis la page publique de cours historiques."""
        base_url = f"{self.BASE_URL}{self.HISTORY_PATH_TEMPLATE.format(symbol=symbol.upper())}"
        rows: list[dict] = []
        seen_dates: set[str] = set()

        for page in range(1, 251):
            url = f"{base_url}?page={page}"
            response = await self.client.get(url)
            if response.status_code in {403, 404}:
                logger.warning(
                    "RichBourse a refuse l'acces a l'historique %s (%s pour %s).",
                    symbol.upper(),
                    response.status_code,
                    url,
                )
                break
            response.raise_for_status()

            parsed_rows = self._extract_history_rows(response.text)
            if not parsed_rows:
                break

            new_rows = [row for row in parsed_rows if row["date"] not in seen_dates]
            if not new_rows:
                break

            rows.extend(new_rows)
            seen_dates.update(row["date"] for row in new_rows)

        return rows

    def _extract_history_rows(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")
        if not tables:
            return []

        target_table = max(tables, key=lambda table: len(table.find_all("tr")))
        rows: list[dict] = []
        headers = [self._normalize_header(cell.get_text(" ", strip=True)) for cell in target_table.find_all("th")]

        for row in target_table.find_all("tr")[1:]:
            cells = row.find_all("td")
            if not cells:
                continue

            values = [cell.get_text(" ", strip=True) for cell in cells]
            record = self._map_history_row(headers, values)
            if record is not None:
                rows.append(record)

        return rows

    def _map_history_row(self, headers: list[str], values: list[str]) -> dict | None:
        if not values:
            return None

        row_map = {headers[i] if i < len(headers) else f"col_{i}": values[i] for i in range(len(values))}
        date_value = self._first_match(row_map, ("date", "jour", "seance"))
        close_value = self._first_match(
            row_map,
            ("coursnormal", "close", "cloture", "coursajuste", "cours", "dernier"),
        )
        volume_value = self._first_match(
            row_map,
            ("volumenormal", "volumeajuste", "volume", "quantite", "titres"),
        )

        if not date_value:
            first = values[0]
            if re.match(r"\d{2}/\d{2}/\d{4}", first):
                date_value = first

        if close_value is None and len(values) >= 2:
            close_value = values[1]
        if volume_value is None and len(values) >= 5:
            volume_value = values[4]

        if not date_value:
            return None

        return {
            "date": date_value,
            "open": self._first_match(row_map, ("open", "ouverture")),
            "high": self._first_match(row_map, ("high", "haut", "plushaut")),
            "low": self._first_match(row_map, ("low", "bas", "plusbas")),
            "close": close_value,
            "volume": volume_value,
        }

    def _normalize_header(self, value: str) -> str:
        normalized = value.lower()
        normalized = normalized.replace("é", "e").replace("è", "e").replace("ê", "e")
        normalized = normalized.replace("à", "a").replace("ù", "u").replace("ô", "o")
        normalized = re.sub(r"[^a-z0-9]+", "", normalized)
        return normalized

    def _first_match(self, row_map: dict[str, str], candidates: tuple[str, ...]) -> str | None:
        for candidate in candidates:
            for key, value in row_map.items():
                if candidate in key:
                    return value
        return None
