from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from brvm_package.db import paths as db_paths
from brvm_package.providers.base import ProviderResult
from brvm_package.providers.router import RoutedResult
from brvm_package.scraper.richbourse import RichbourseClient
from brvm_package.scraper.sikafinance import SikaFinanceClient
from brvm_package.services import sync as sync_module
from brvm_package.data.catalog import get_sika_ticker


def test_database_path_seeds_user_copy_when_needed(tmp_path, monkeypatch) -> None:
    seed_path = tmp_path / "seed.sqlite3"
    seed_bytes = b"seed-db"
    seed_path.write_bytes(seed_bytes)
    target_path = tmp_path / ".brvm" / "brvm.sqlite3"

    monkeypatch.delenv("BRVM_DATABASE_URL", raising=False)
    monkeypatch.delenv("BRVM_DATABASE_PATH", raising=False)
    monkeypatch.setattr(db_paths, "DEFAULT_USER_DB_PATH", target_path)
    monkeypatch.setattr(db_paths, "_source_tree_database_path", lambda: None)
    monkeypatch.setattr(db_paths, "_seed_database_path", lambda: seed_path)

    resolved_path = db_paths.get_database_path()

    assert resolved_path == target_path
    assert resolved_path.exists()
    assert resolved_path.read_bytes() == seed_bytes


def test_sync_market_data_falls_back_to_catalog_symbols(monkeypatch) -> None:
    async def fake_init_db() -> None:
        return None

    async def fake_upsert_ticker_quotes(rows: list[dict[str, object]]) -> int:
        return len(rows)

    async def fake_upsert_daily_prices(symbol: str, rows: list[dict[str, object]]) -> int:
        return len(rows)

    async def fake_upsert_fundamental_snapshot(symbol: str, info: dict[str, object]) -> int:
        return 1 if info else 0

    async def fake_get_last_price_date(symbol: str):
        return None

    class FakeRouter:
        async def get_market_quotes(self) -> RoutedResult:
            return RoutedResult(
                result=ProviderResult(
                    provider="richbourse",
                    data=[],
                    success=False,
                    error="Aucune cotation consolidee exploitable trouvee sur RichBourse.",
                ),
                attempts=[{"provider": "richbourse", "status": "empty"}],
            )

        async def get_history(self, symbol: str, start_date: str, end_date: str) -> RoutedResult:
            return RoutedResult(
                result=ProviderResult(
                    provider="sikafinance",
                    data=[
                        {
                            "Date": "17/04/2026",
                            "Open": 100.0,
                            "High": 101.0,
                            "Low": 99.0,
                            "Close": 100.0,
                            "Volume": 10,
                            "source": "sikafinance",
                        }
                    ],
                    success=True,
                ),
                attempts=[{"provider": "sikafinance", "status": "success"}],
            )

        async def get_fundamentals(self, symbol: str) -> RoutedResult:
            return RoutedResult(
                result=ProviderResult(
                    provider="sikafinance",
                    data={
                        "symbol": symbol,
                        "revenue": 1000.0,
                        "net_income": 100.0,
                        "eps": 10.0,
                        "per": 10.0,
                        "dividend": 1.0,
                        "source": "sikafinance",
                    },
                    success=True,
                ),
                attempts=[{"provider": "sikafinance", "status": "success"}],
            )

    monkeypatch.setattr(sync_module, "init_db", fake_init_db)
    monkeypatch.setattr(sync_module, "_upsert_ticker_quotes", fake_upsert_ticker_quotes)
    monkeypatch.setattr(sync_module, "_upsert_daily_prices", fake_upsert_daily_prices)
    monkeypatch.setattr(sync_module, "_upsert_fundamental_snapshot", fake_upsert_fundamental_snapshot)
    monkeypatch.setattr(sync_module, "_get_last_price_date", fake_get_last_price_date)
    monkeypatch.setattr(sync_module, "DataRouter", FakeRouter)
    monkeypatch.setattr(sync_module, "get_available_symbols", lambda: [])
    monkeypatch.setattr(
        sync_module,
        "get_asset_catalog",
        lambda: {"SNTS": {"name": "Sonatel"}, "BOAB": {"name": "BOA Benin"}},
    )

    result = asyncio.run(sync_module.sync_market_data(max_concurrency=3))

    assert result["symbols"] == 2
    assert result["history_rows_upserted"] == 2
    assert result["fundamental_snapshots_saved"] == 2
    assert result["max_concurrency"] == 3
    assert set(result["details"]) == {"SNTS", "BOAB"}
    assert any(
        attempt["provider"] == "catalog" and "fallback" in attempt["status"]
        for attempt in result["market_attempts"]
    )


def test_richbourse_market_quotes_handles_forbidden(monkeypatch) -> None:
    class FakeClient:
        async def get(self, url: str) -> httpx.Response:
            request = httpx.Request("GET", url)
            return httpx.Response(status_code=403, request=request, text="forbidden")

    client = RichbourseClient()
    client.client = FakeClient()

    rows = asyncio.run(client.get_market_quotes())

    assert rows == []


def test_richbourse_history_uses_public_historical_page_and_parses_rows(monkeypatch) -> None:
    requested_urls: list[str] = []
    html_page = """
    <html>
      <body>
        <table>
          <tr>
            <th>Date</th>
            <th>Variation (%)</th>
            <th>Valeur (FCFA)</th>
            <th>Cours ajusté</th>
            <th>Volume ajusté</th>
            <th>Cours normal</th>
            <th>Volume normal</th>
          </tr>
          <tr>
            <td>17/04/2026</td>
            <td>0.43%</td>
            <td>10 000 000</td>
            <td>28 800</td>
            <td>1 200</td>
            <td>28 800</td>
            <td>1 200</td>
          </tr>
        </table>
      </body>
    </html>
    """

    class FakeClient:
        async def get(self, url: str) -> httpx.Response:
            requested_urls.append(url)
            request = httpx.Request("GET", url)
            if url.endswith("?page=1"):
                return httpx.Response(status_code=200, request=request, text=html_page)
            return httpx.Response(status_code=200, request=request, text="<html><body></body></html>")

    client = RichbourseClient()
    client.client = FakeClient()

    rows = asyncio.run(client.get_historical_prices("SNTS"))

    assert requested_urls[0].endswith("/common/variation/historique/SNTS?page=1")
    assert rows == [
        {
            "date": "17/04/2026",
            "open": None,
            "high": None,
            "low": None,
            "close": "28 800",
            "volume": "1 200",
        }
    ]


def test_richbourse_market_quotes_parse_public_variation_table(monkeypatch) -> None:
    html_page = """
    <html>
      <body>
        <table>
          <tr>
            <th>Symbole</th>
            <th>Action</th>
            <th>Variation</th>
            <th>Volume</th>
            <th>Valeur (FCFA)</th>
            <th>Cours actuel</th>
            <th>Cours de la veille</th>
            <th>Capitalisation</th>
          </tr>
          <tr>
            <td>TOTAL</td>
            <td></td>
            <td></td>
            <td>1 000</td>
            <td>2 000 000</td>
            <td></td>
            <td></td>
            <td></td>
          </tr>
          <tr>
            <td>SNTS</td>
            <td>SONATEL</td>
            <td>0.43%</td>
            <td>13 795</td>
            <td>385 666 860</td>
            <td>28 100</td>
            <td>27 995</td>
            <td>2 880 000 000 000</td>
          </tr>
        </table>
      </body>
    </html>
    """

    class FakeClient:
        async def get(self, url: str) -> httpx.Response:
            request = httpx.Request("GET", url)
            return httpx.Response(status_code=200, request=request, text=html_page)

    client = RichbourseClient()
    client.client = FakeClient()

    rows = asyncio.run(client.get_market_quotes())

    assert rows == [
        {
            "symbol": "SNTS",
            "price": "28 100",
            "variation": "0.43%",
            "volume": "13 795",
            "value_traded": "385 666 860",
        }
    ]


def test_sika_ticker_resolution_uses_country_suffixes() -> None:
    assert get_sika_ticker("SNTS") == "SNTS.sn"
    assert get_sika_ticker("BOABF") == "BOABF.bf"
    assert get_sika_ticker("BOAB") == "BOAB.bj"
    assert get_sika_ticker("ETIT") == "ETIT.tg"
    assert get_sika_ticker("BOAM") == "BOAM.ml"


def test_sikafinance_ticker_info_extracts_verified_metadata(monkeypatch) -> None:
    society_html = """
    <html>
      <body>
        Nombre de titres : 100 000 000
        Flottant : 22,47%
        Valorisation de la société : 2 835 000 MFCFA
        Principaux actionnaires
        FRANCE TELECOM*42,3;ETAT DU SENEGAL*27,7;PUBLIC (BRVM)*20;EMPLOYES SONATEL*10
        Les chiffres sont en millions de FCFA
        <table></table>
        <table>
          <tr><th>Libellé</th><th>2024</th><th>2025</th></tr>
          <tr><td>Chiffre d'affaires</td><td>1 776 443</td><td>1 923 122</td></tr>
          <tr><td>Résultat net</td><td>393 662</td><td>413 588</td></tr>
          <tr><td>BNPA</td><td>3 937,00</td><td>4 136,00</td></tr>
          <tr><td>PER</td><td>7,20</td><td>6,85</td></tr>
          <tr><td>Dividende</td><td>1 655,00</td><td>1 740,00</td></tr>
        </table>
      </body>
    </html>
    """
    quote_html = """
    <html>
      <body>
        Beta 1 an | 0,74
        Valorisation | 2 880 000 MXOF
      </body>
    </html>
    """

    async def fake_fetch_page(self: SikaFinanceClient, endpoint: str) -> str:
        if endpoint.startswith("/marches/societe/"):
            return society_html
        if endpoint.startswith("/marches/cotation_"):
            return quote_html
        raise AssertionError(endpoint)

    monkeypatch.setattr(SikaFinanceClient, "_fetch_page", fake_fetch_page)

    client = SikaFinanceClient()
    info = asyncio.run(client.get_ticker_info("SNTS"))

    assert info["symbol"] == "SNTS"
    assert info["revenue"] == 1_923_122_000_000.0
    assert info["net_income"] == 413_588_000_000.0
    assert info["eps"] == 4136.0
    assert info["per"] == 6.85
    assert info["dividend"] == 1740.0
    assert info["shares_outstanding"] == 100_000_000.0
    assert info["float_ratio"] == 22.47
    assert info["market_cap"] == 2_835_000_000_000.0
    assert info["beta_1y"] == 0.74
    assert "FRANCE TELECOM" in info["major_shareholders"]
