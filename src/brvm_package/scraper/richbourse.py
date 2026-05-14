from __future__ import annotations

import os
import re
import time
import logging
from datetime import date, datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

RETRY_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.NetworkError,
    httpx.HTTPStatusError,
)


class RichbourseClient:
    """Client asynchrone robuste pour extraire les données depuis RichBourse."""

    BASE_URL = "https://www.richbourse.com"
    MARKET_QUOTES_PATH = "/common/variation/index/veille/tout"
    HISTORY_PATH_TEMPLATE = "/common/variation/historique/{symbol}"
    DEFAULT_TIMEOUT = 30.0
    MAX_HISTORY_PAGES = 250

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, max_history_pages: int | None = None) -> None:
        self.timeout = timeout
        self.max_history_pages = self._resolve_max_history_pages(max_history_pages)
        self.last_history_diagnostics: dict[str, Any] = {}
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient | None:
        return self._client

    @client.setter
    def client(self, value: httpx.AsyncClient | None) -> None:
        self._client = value

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or getattr(self._client, "is_closed", False):
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
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
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "RichbourseClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=10),
        retry=retry_if_exception_type(RETRY_EXCEPTIONS),
        reraise=True,
    )
    async def get_market_quotes(self) -> list[dict]:
        """Récupère les cotations générales consolidées du marché."""
        url = f"{self.BASE_URL}{self.MARKET_QUOTES_PATH}"
        client = await self._get_client()
        t0 = time.monotonic()
        response = await client.get(url)
        elapsed = time.monotonic() - t0
        logger.debug("RichBourse market quotes | status=%s | time=%.2fs", response.status_code, elapsed)

        if response.status_code in {403, 404}:
            logger.warning(
                "RichBourse a refuse l'acces aux cotations consolidees (%s pour %s).",
                response.status_code,
                url,
            )
            return []
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        results: list[dict] = []
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

        logger.info("RichBourse market quotes: %d rows fetched in %.2fs", len(results), elapsed)
        return results

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=10),
        retry=retry_if_exception_type(RETRY_EXCEPTIONS),
        reraise=True,
    )
    async def get_historical_prices(
        self,
        symbol: str,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
        max_pages: int | None = None,
    ) -> list[dict]:
        """Récupère l'historique quotidien depuis la page publique de cours historiques."""
        base_url = f"{self.BASE_URL}{self.HISTORY_PATH_TEMPLATE.format(symbol=symbol.upper())}"
        rows: list[dict] = []
        seen_dates: set[str] = set()
        client = await self._get_client()
        page_limit = self._resolve_max_history_pages(max_pages)
        start_dt = self._parse_date(start_date)
        end_dt = self._parse_date(end_date)
        if start_dt is not None and end_dt is not None and start_dt > end_dt:
            raise ValueError("start_date must be <= end_date")

        pages_fetched = 0
        for page in range(1, page_limit + 1):
            url = f"{base_url}?page={page}"
            t0 = time.monotonic()
            response = await client.get(url)
            elapsed = time.monotonic() - t0
            pages_fetched = page
            logger.debug(
                "RichBourse history %s page=%d | status=%s | time=%.2fs",
                symbol.upper(),
                page,
                response.status_code,
                elapsed,
            )

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
                logger.info("RichBourse history %s: no more rows at page %d", symbol.upper(), page)
                break

            new_rows = [row for row in parsed_rows if row["date"] not in seen_dates]
            if not new_rows:
                logger.info("RichBourse history %s: no new rows at page %d", symbol.upper(), page)
                break

            seen_dates.update(row["date"] for row in new_rows)
            dated_rows = [(row, self._parse_date(row.get("date"))) for row in new_rows]
            page_dates = [row_date for _, row_date in dated_rows if row_date is not None]

            if start_dt is None and end_dt is None:
                rows.extend(new_rows)
            else:
                rows.extend(
                    row
                    for row, row_date in dated_rows
                    if row_date is not None
                    and (start_dt is None or row_date >= start_dt)
                    and (end_dt is None or row_date <= end_dt)
                )

            if start_dt is not None and page_dates and max(page_dates) < start_dt:
                logger.info(
                    "RichBourse history %s: stopped at page %d because page is older than %s",
                    symbol.upper(),
                    page,
                    start_dt,
                )
                break

        logger.info(
            "RichBourse history %s: %d total rows across %d/%d pages",
            symbol.upper(),
            len(rows),
            pages_fetched,
            page_limit,
        )
        self.last_history_diagnostics = {
            "symbol": symbol.upper(),
            "rows": len(rows),
            "pages_fetched": pages_fetched,
            "page_limit": page_limit,
            "start_date": start_dt.isoformat() if start_dt is not None else None,
            "end_date": end_dt.isoformat() if end_dt is not None else None,
        }
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

    def _resolve_max_history_pages(self, max_pages: int | None) -> int:
        if max_pages is not None:
            return max(1, int(max_pages))

        env_value = os.getenv("BRVM_RICHBOURSE_MAX_HISTORY_PAGES")
        if env_value:
            try:
                return max(1, int(env_value))
            except ValueError:
                logger.warning(
                    "Invalid BRVM_RICHBOURSE_MAX_HISTORY_PAGES=%r; using default %d",
                    env_value,
                    self.MAX_HISTORY_PAGES,
                )
        return self.MAX_HISTORY_PAGES

    def _parse_date(self, value: str | date | None) -> date | None:
        if value is None:
            return None
        if isinstance(value, date):
            return value

        text = str(value).strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None
