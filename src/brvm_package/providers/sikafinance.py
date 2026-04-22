from __future__ import annotations

from typing import Any

from brvm_package.providers.base import MarketDataProvider, ProviderResult
from brvm_package.scraper.sikafinance import SikaFinanceClient


class SikaFinanceProvider(MarketDataProvider):
    name = "sikafinance"

    def __init__(self) -> None:
        self.client = SikaFinanceClient()

    async def get_market_quotes(self) -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            data=[],
            success=False,
            error="SikaFinanceProvider ne fournit pas encore les cotations marche consolidees.",
        )

    async def get_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> ProviderResult:
        try:
            rows = await self.client.get_historical_data(symbol, start_date, end_date, period=0)
            normalized = [self._normalize_history_row(symbol, row) for row in rows]
            normalized = [row for row in normalized if row is not None]
            return ProviderResult(provider=self.name, data=normalized, success=True)
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(provider=self.name, data=[], success=False, error=str(exc))

    async def get_fundamentals(self, symbol: str) -> ProviderResult:
        try:
            info = await self.client.get_ticker_info(symbol)
            normalized = {
                "symbol": symbol.upper(),
                "revenue": self._to_float(info.get("revenue")),
                "net_income": self._to_float(info.get("net_income")),
                "eps": self._to_float(info.get("eps")),
                "per": self._to_float(info.get("per")),
                "dividend": self._to_float(info.get("dividend") or info.get("dividend_yield")),
                "market_cap": self._to_float(info.get("market_cap")),
                "pbr": self._to_float(info.get("pbr")),
                "roe": self._to_float(info.get("roe")),
                "shares_outstanding": self._to_float(info.get("shares_outstanding")),
                "float_ratio": self._to_float(info.get("float_ratio")),
                "beta_1y": self._to_float(info.get("beta_1y")),
                "major_shareholders": info.get("major_shareholders"),
                "source": self.name,
            }
            if not self._has_meaningful_fundamentals(normalized):
                return ProviderResult(
                    provider=self.name,
                    data={},
                    success=False,
                    error=f"Aucune donnee fondamentale exploitable pour {symbol}.",
                )
            return ProviderResult(provider=self.name, data=normalized, success=True)
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(provider=self.name, data={}, success=False, error=str(exc))

    def _normalize_history_row(self, symbol: str, row: dict[str, Any]) -> dict[str, Any] | None:
        date_value = row.get("Date")
        if not date_value:
            return None

        return {
            "symbol": symbol.upper(),
            "Date": str(date_value),
            "Open": self._to_float(row.get("Open")),
            "High": self._to_float(row.get("High")),
            "Low": self._to_float(row.get("Low")),
            "Close": self._to_float(row.get("Close") or row.get("Cloture") or row.get("Valeur")),
            "Volume": self._to_int(row.get("Volume")),
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

    def _has_meaningful_fundamentals(self, info: dict[str, Any]) -> bool:
        meaningful_fields = (
            "revenue",
            "net_income",
            "eps",
            "per",
            "dividend",
            "market_cap",
            "pbr",
            "roe",
            "shares_outstanding",
            "float_ratio",
        )
        return any(info.get(field) is not None for field in meaningful_fields)
