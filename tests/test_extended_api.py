from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import brvm as bv


def test_fundamentals_and_screen() -> None:
    market_cap = bv.market_cap("SNTS")
    assert market_cap["symbol"] == "SNTS"
    assert "market_cap" in market_cap
    assert not bv.market_cap_all().empty
    assert not bv.screen(min_market_cap=0).empty
    assert not bv.fundamental_history("SNTS").empty
    assert "fundamental_history" in bv.financials("SNTS")


def test_portfolio_and_backtest() -> None:
    portfolio = bv.Portfolio(["SNTS", "BOAC"])
    weights = portfolio.optimize(method="min_vol")
    assert set(weights) == {"SNTS", "BOAC"}
    report = portfolio.backtest(transaction_cost=0.001, slippage_bps=5.0)
    assert report["summary"]["final_value"] > 0
    assert "cost_paid" in report["summary"]
    assert report["transactions"] is not None


def test_macro_and_plotting_interfaces() -> None:
    assert not bv.fcfa_exchange_rates().empty
    assert not bv.inflation().empty
    assert not bv.macro_events().empty
    assert bv.candlestick("SNTS") is not None
    assert bv.heatmap() is not None


def test_advanced_screen_filters() -> None:
    frame = bv.screen(
        query="bank",
        filters={"market_cap": (">=", 0), "country": ("contains", "cote")},
        sort_by="market_cap",
        limit=5,
    )
    assert frame is not None


def test_sector_labels_and_aliases() -> None:
    sectors = bv.list_sectors()
    assert "Services Financiers" in sectors
    assert "Télécommunications" in sectors
    frame = bv.screen(sector="Banking", limit=10)
    assert not frame.empty
    assert set(frame["sector"].dropna().unique()) == {"Services Financiers"}
