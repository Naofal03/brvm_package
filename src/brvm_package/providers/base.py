from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ProviderResult:
    provider: str
    data: Any
    success: bool
    error: str | None = None


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    async def get_market_quotes(self) -> ProviderResult:
        raise NotImplementedError

    @abstractmethod
    async def get_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> ProviderResult:
        raise NotImplementedError

    @abstractmethod
    async def get_fundamentals(self, symbol: str) -> ProviderResult:
        raise NotImplementedError
