"""Tests d'intégration live — appellent les vrais endpoints BRVM/SikaFinance/RichBourse.
Désactivés par défaut. Activez-les avec :
    export BRVM_LIVE_TESTS=1
    pytest tests/test_integration_live.py -v
"""

from __future__ import annotations

import asyncio
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("BRVM_LIVE_TESTS") not in {"1", "true", "yes"},
    reason="BRVM_LIVE_TESTS non activé. Activez avec BRVM_LIVE_TESTS=1.",
)


@pytest.mark.asyncio
async def test_sikafinance_historical_data() -> None:
    from brvm_package.scraper.sikafinance import SikaFinanceClient

    client = SikaFinanceClient()
    try:
        rows = await client.get_historical_data("SNTS", "2024-01-01", "2024-01-31", period=0)
        assert len(rows) > 0
        first = rows[0]
        assert "Date" in first
        assert "Close" in first
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_sikafinance_ticker_info() -> None:
    from brvm_package.scraper.sikafinance import SikaFinanceClient

    client = SikaFinanceClient()
    try:
        info = await client.get_ticker_info("SNTS")
        assert isinstance(info, dict)
        assert info.get("symbol") == "SNTS"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_richbourse_market_quotes() -> None:
    from brvm_package.scraper.richbourse import RichbourseClient

    client = RichbourseClient()
    try:
        rows = await client.get_market_quotes()
        assert isinstance(rows, list)
        if rows:
            assert "symbol" in rows[0]
            assert "price" in rows[0]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_richbourse_historical_prices() -> None:
    from brvm_package.scraper.richbourse import RichbourseClient

    client = RichbourseClient()
    try:
        rows = await client.get_historical_prices("SNTS")
        assert isinstance(rows, list)
        if rows:
            assert "date" in rows[0]
            assert "close" in rows[0]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_provider_router_fundamentals() -> None:
    from brvm_package.providers.router import DataRouter

    async with DataRouter() as router:
        result = await router.get_fundamentals("SNTS")
        assert result.result is not None
        assert len(result.attempts) > 0
        assert any(a["provider"] in {"sikafinance", "richbourse", "brvm"} for a in result.attempts)


def test_sync_market_data_cli() -> None:
    from brvm_package.services.sync import sync_market_data

    result = asyncio.run(sync_market_data(symbol="SNTS"))
    assert "symbols" in result
    assert result["symbols"] >= 1


def test_financial_reports_api() -> None:
    from brvm_package.financial_reports.api import get_financials, list_available_years

    years = list_available_years("SNTS")
    assert isinstance(years, list)
    if years:
        data = get_financials("SNTS", fiscal_year=years[-1])
        assert isinstance(data, dict)


def test_data_access_report_snapshot() -> None:
    from brvm_package.data.access import _get_last_report_snapshot

    snap = _get_last_report_snapshot("SNTS")
    if snap is not None:
        assert "symbol" in snap


def test_valuation_ratios_fields() -> None:
    from brvm_package.fundamentals.core import valuation_ratios

    ratios = valuation_ratios("SNTS")
    assert isinstance(ratios, dict)
    assert ratios.get("symbol") == "SNTS"
    assert "PER" in ratios
    assert "ROE" in ratios
