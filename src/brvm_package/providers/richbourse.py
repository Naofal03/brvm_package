from __future__ import annotations

from typing import Any

from brvm_package.providers.base import MarketDataProvider, ProviderResult
from brvm_package.scraper.richbourse import RichbourseClient


class RichBourseProvider(MarketDataProvider):
    name = "richbourse"

    def __init__(self) -> None:
        self.client = RichbourseClient()

    async def get_market_quotes(self) -> ProviderResult:
        try:
            rows = await self.client.get_market_quotes()
            normalized = [self._normalize_quote_row(row) for row in rows]
            normalized = [row for row in normalized if row is not None]
            if not normalized:
                return ProviderResult(
                    provider=self.name,
                    data=[],
                    success=False,
                    error="Aucune cotation consolidee exploitable trouvee sur RichBourse.",
                )
            return ProviderResult(provider=self.name, data=normalized, success=True)
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(provider=self.name, data=[], success=False, error=str(exc))

    async def get_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> ProviderResult:
        try:
            rows = await self.client.get_historical_prices(symbol)
            normalized = [self._normalize_history_row(symbol, row) for row in rows]
            normalized = [row for row in normalized if row is not None]
            return ProviderResult(provider=self.name, data=normalized, success=True)
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(provider=self.name, data=[], success=False, error=str(exc))

    async def get_fundamentals(self, symbol: str) -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            data={},
            success=False,
            error=f"Fondamentaux indisponibles via RichBourseProvider pour {symbol}.",
        )

    def _normalize_quote_row(self, row: dict[str, Any]) -> dict[str, Any] | None:
        symbol = row.get("symbol")
        if not symbol:
            return None

        return {
            "symbol": str(symbol).upper(),
            "price": self._to_float(row.get("price")),
            "variation": row.get("variation"),
            "volume": self._to_int(row.get("volume")),
            "value_traded": self._to_float(row.get("value_traded")),
            "source": self.name,
        }

    def _normalize_history_row(self, symbol: str, row: dict[str, Any]) -> dict[str, Any] | None:
        date_value = row.get("date")
        if not date_value:
            return None

        return {
            "symbol": symbol.upper(),
            "Date": str(date_value),
            "Open": self._to_float(row.get("open")),
            "High": self._to_float(row.get("high")),
            "Low": self._to_float(row.get("low")),
            "Close": self._to_float(row.get("close")),
            "Volume": self._to_int(row.get("volume")),
            "source": self.name,
        }

    def _to_float(self, value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip().replace("\xa0", " ").replace(" ", "")
        text = text.replace("FCFA", "").replace("XOF", "").replace("%", "").replace(",", ".")
        if text in {"", "-", "--", "N/A", "null"}:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _to_int(self, value: Any) -> int | None:
        converted = self._to_float(value)
        if converted is None:
            return None
        return int(converted)
