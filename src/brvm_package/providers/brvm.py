from __future__ import annotations

from brvm_package.providers.base import MarketDataProvider, ProviderResult


class BRVMProvider(MarketDataProvider):
    name = "brvm"

    async def get_market_quotes(self) -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            data=[],
            success=False,
            error="BRVMProvider non implemente pour le moment.",
        )

    async def get_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            data=[],
            success=False,
            error=f"Historique indisponible via BRVMProvider pour {symbol}.",
        )

    async def get_fundamentals(self, symbol: str) -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            data={},
            success=False,
            error=f"Fondamentaux indisponibles via BRVMProvider pour {symbol}.",
        )
