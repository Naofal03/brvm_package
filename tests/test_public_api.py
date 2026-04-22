from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import brvm as bv


def test_public_api_smoke() -> None:
    assert "SNTS" in bv.list_assets()
    assert "BOABF" in bv.list_assets()
    assert len(bv.list_assets()) >= 47
    assert bv.list_stocks() == bv.list_assets()
    assert not bv.search("bank").empty
    assert bv.live_price("SNTS") is not None
    assert not bv.download("SNTS", period="1mo").empty


def test_ticker_object_smoke() -> None:
    ticker = bv.Ticker("SNTS")
    assert ticker.info["symbol"] == "SNTS"
    assert not ticker.history(period="1y").empty
    assert not ticker.returns().empty


def test_ticker_history_period_filters_rows() -> None:
    ticker = bv.Ticker("SNTS")
    full_history = ticker.history()
    recent_history = ticker.history(period="1mo")

    assert not full_history.empty
    assert not recent_history.empty
    assert len(recent_history) < len(full_history)
    assert recent_history.index.min() >= full_history.index.max() - bv.Ticker("SNTS")._parse_period("1mo")
