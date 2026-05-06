from __future__ import annotations

import time
from dataclasses import dataclass

from brvm_package.providers.base import MarketDataProvider, ProviderResult
from brvm_package.providers.brvm import BRVMProvider
from brvm_package.providers.richbourse import RichBourseProvider
from brvm_package.providers.sikafinance import SikaFinanceProvider


@dataclass
class RoutedResult:
    result: ProviderResult
    attempts: list[dict[str, str]]


class DataRouter:
    def __init__(self) -> None:
        self.providers: list[MarketDataProvider] = [
            BRVMProvider(),
            SikaFinanceProvider(),
            RichBourseProvider(),
        ]

    async def close(self) -> None:
        for provider in self.providers:
            if hasattr(provider, "close"):
                await provider.close()

    async def __aenter__(self) -> "DataRouter":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def get_market_quotes(self) -> RoutedResult:
        return await self._first_success("get_market_quotes")

    async def get_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> RoutedResult:
        return await self._first_success("get_history", symbol, start_date, end_date)

    async def get_fundamentals(self, symbol: str) -> RoutedResult:
        return await self._first_success("get_fundamentals", symbol)

    async def _first_success(self, method_name: str, *args: str) -> RoutedResult:
        attempts: list[dict[str, str]] = []
        last_result: ProviderResult | None = None

        for provider in self.providers:
            method = getattr(provider, method_name)
            t0 = time.monotonic()
            result: ProviderResult = await method(*args)
            elapsed = time.monotonic() - t0
            last_result = result

            if result.success and self._has_payload(result.data):
                attempts.append(
                    {
                        "provider": provider.name,
                        "status": "success",
                        "elapsed_ms": f"{elapsed * 1000:.1f}",
                    }
                )
                return RoutedResult(result=result, attempts=attempts)

            attempts.append(
                {
                    "provider": provider.name,
                    "status": result.error or "empty",
                    "elapsed_ms": f"{elapsed * 1000:.1f}",
                }
            )

        assert last_result is not None
        return RoutedResult(result=last_result, attempts=attempts)

    def _has_payload(self, data: object) -> bool:
        if isinstance(data, dict):
            return len(data) > 0
        if isinstance(data, list):
            return len(data) > 0
        return data is not None

