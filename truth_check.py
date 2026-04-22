from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import brvm as bv


CheckFunc = Callable[[], Any]


@dataclass
class ValidationReport:
    passed: int = 0
    failed: int = 0
    failures: list[dict[str, str]] = field(default_factory=list)

    def run(self, label: str, func: CheckFunc) -> Any:
        try:
            result = func()
            self.passed += 1
            return result
        except Exception as exc:  # noqa: BLE001
            self.failed += 1
            self.failures.append({"check": label, "error": f"{type(exc).__name__}: {exc}"})
            return None


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _not_empty_frame(frame: Any, label: str) -> None:
    _assert(hasattr(frame, "empty"), f"{label}: objet sans attribut empty")
    _assert(not frame.empty, f"{label}: DataFrame/Series vide")


def validate_global_api(report: ValidationReport, symbols: list[str]) -> None:
    report.run("api.list_assets", lambda: _assert(len(bv.list_assets()) >= 47, "univers BRVM trop petit"))
    report.run("api.list_stocks", lambda: _assert(bv.list_stocks() == symbols, "list_stocks differe de list_assets"))
    report.run("api.list_indices", lambda: _assert(len(bv.list_indices()) >= 5, "indices BRVM manquants"))
    report.run("api.list_indices_detailed", lambda: _not_empty_frame(bv.list_indices(detailed=True), "list_indices(detailed=True)"))
    report.run("api.list_sectors", lambda: _assert(len(bv.list_sectors()) >= 5, "secteurs BRVM manquants"))
    report.run("api.list_countries", lambda: _assert(len(bv.list_countries()) >= 5, "pays BRVM manquants"))
    report.run("api.market_summary", lambda: _assert(bool(bv.market_summary()), "market_summary vide"))
    report.run("api.search", lambda: _not_empty_frame(bv.search("bank"), "search('bank')"))
    report.run("api.download_all", lambda: _not_empty_frame(bv.download_all(period="1mo"), "download_all(period='1mo')"))
    report.run("api.market_cap_all", lambda: _not_empty_frame(bv.market_cap_all(), "market_cap_all()"))
    report.run("api.fcfa_exchange_rates", lambda: _not_empty_frame(bv.fcfa_exchange_rates(), "fcfa_exchange_rates()"))
    report.run("api.inflation", lambda: _not_empty_frame(bv.inflation(), "inflation()"))
    report.run("api.macro_events", lambda: _not_empty_frame(bv.macro_events(), "macro_events()"))
    report.run("api.candlestick", lambda: _assert(bv.candlestick(symbols[0], period="1mo") is not None, "candlestick None"))
    report.run("api.heatmap", lambda: _assert(bv.heatmap(symbols[:10]) is not None, "heatmap None"))
    report.run(
        "api.sector_allocation",
        lambda: _assert(bv.sector_allocation({symbols[0]: 0.5, symbols[1]: 0.5}) is not None, "sector_allocation None"),
    )


def validate_market_object(report: ValidationReport, symbols: list[str]) -> None:
    market = bv.get_market()
    report.run("market.assets", lambda: _assert(len(market.assets()) == len(symbols), "Market.assets incoherent"))
    report.run("market.indices", lambda: _assert(len(market.indices()) >= 5, "Market.indices vide"))
    report.run("market.indices_detailed", lambda: _not_empty_frame(market.indices(detailed=True), "Market.indices(detailed=True)"))
    report.run("market.sectors", lambda: _assert(len(market.sectors()) >= 5, "Market.sectors vide"))
    report.run("market.countries", lambda: _assert(len(market.countries()) >= 5, "Market.countries vide"))
    report.run("market.summary", lambda: _assert(bool(market.summary()), "Market.summary vide"))
    report.run("market.info", lambda: _assert(market.info(symbols[0]).get("symbol") == symbols[0], "Market.info invalide"))
    report.run("market.screen", lambda: _not_empty_frame(market.screen(limit=5), "Market.screen"))
    report.run("market.returns_matrix", lambda: _not_empty_frame(market.returns_matrix(symbols[:10]), "Market.returns_matrix"))


def validate_index_object(report: ValidationReport) -> None:
    index = bv.Index("BRVM-C")
    report.run("index.info", lambda: _assert(index.info is not None, "Index.info vide"))
    report.run("index.history", lambda: _not_empty_frame(index.history(), "Index.history"))


def validate_symbol_surface(report: ValidationReport, symbol: str) -> None:
    ticker = bv.Ticker(symbol)

    report.run(f"{symbol}.api.asset_info", lambda: _assert(bv.asset_info(symbol).get("symbol") == symbol, "asset_info invalide"))
    report.run(f"{symbol}.api.download_period", lambda: _not_empty_frame(bv.download(symbol, period="1mo"), f"download({symbol}, period='1mo')"))
    report.run(
        f"{symbol}.api.download_range",
        lambda: _not_empty_frame(bv.download(symbol, start="2026-01-01", end="2026-04-17"), f"download({symbol}, range)"),
    )
    report.run(f"{symbol}.api.live_price", lambda: _assert(bv.live_price(symbol) is not None, "live_price None"))
    report.run(f"{symbol}.api.returns", lambda: _not_empty_frame(bv.returns(symbol), f"returns({symbol})"))
    report.run(f"{symbol}.api.market_cap", lambda: _assert(bv.market_cap(symbol).get("symbol") == symbol, "market_cap invalide"))
    report.run(f"{symbol}.api.shares_outstanding", lambda: bv.shares_outstanding(symbol))
    report.run(f"{symbol}.api.dividends", lambda: bv.dividends(symbol))
    report.run(f"{symbol}.api.financials", lambda: _assert("fundamental_history" in bv.financials(symbol), "financials incomplet"))
    report.run(f"{symbol}.api.fundamental_history", lambda: bv.fundamental_history(symbol))
    report.run(f"{symbol}.api.valuation_ratios", lambda: _assert(bv.valuation_ratios(symbol).get("symbol") == symbol, "valuation invalide"))

    report.run(f"{symbol}.ticker.info", lambda: _assert(ticker.info.get("symbol") == symbol, "Ticker.info invalide"))
    report.run(f"{symbol}.ticker.history_period", lambda: _not_empty_frame(ticker.history(period="1mo"), f"{symbol} history(period)"))
    report.run(f"{symbol}.ticker.history_range", lambda: _not_empty_frame(ticker.history(start="2026-01-01", end="2026-04-17"), f"{symbol} history(range)"))
    report.run(f"{symbol}.ticker.live_price", lambda: _assert(ticker.live_price() is not None, "Ticker.live_price None"))
    report.run(f"{symbol}.ticker.returns", lambda: _not_empty_frame(ticker.returns(), f"{symbol} ticker.returns"))
    report.run(f"{symbol}.ticker.volatility", lambda: ticker.volatility())
    report.run(f"{symbol}.ticker.dividends", lambda: ticker.dividends())
    report.run(f"{symbol}.ticker.financials", lambda: _assert("fundamental_history" in ticker.financials(), "Ticker.financials incomplet"))
    report.run(f"{symbol}.ticker.fundamental_history", lambda: ticker.fundamental_history())
    report.run(f"{symbol}.ticker.valuation", lambda: _assert(ticker.valuation().get("symbol") == symbol, "Ticker.valuation invalide"))
    report.run(f"{symbol}.ticker.plot", lambda: _assert(ticker.plot(period="1mo") is not None, "Ticker.plot None"))


def validate_portfolio_and_strategies(report: ValidationReport, symbols: list[str]) -> None:
    subset = symbols[:5]
    all_assets = symbols

    portfolio_all = bv.Portfolio(all_assets)
    report.run("portfolio_all.history", lambda: _not_empty_frame(portfolio_all.history(start="2026-01-01", end="2026-04-17"), "Portfolio(all).history"))
    report.run("portfolio_all.returns", lambda: _not_empty_frame(portfolio_all.returns(start="2026-01-01", end="2026-04-17"), "Portfolio(all).returns"))
    report.run("portfolio_all.performance", lambda: _assert(bool(portfolio_all.performance()), "Portfolio(all).performance vide"))
    report.run("portfolio_all.drawdown", lambda: _not_empty_frame(portfolio_all.drawdown(), "Portfolio(all).drawdown"))
    report.run("portfolio_all.rebalance", lambda: _assert(bool(portfolio_all.rebalance()), "Portfolio(all).rebalance vide"))
    report.run("portfolio_all.sector_exposure", lambda: _not_empty_frame(portfolio_all.sector_exposure(), "Portfolio(all).sector_exposure"))
    report.run("portfolio_all.country_exposure", lambda: _not_empty_frame(portfolio_all.country_exposure(), "Portfolio(all).country_exposure"))
    report.run("portfolio_all.plot_allocation", lambda: _assert(portfolio_all.plot_allocation() is not None, "Portfolio(all).plot_allocation None"))

    portfolio_small = bv.Portfolio(subset)
    report.run("portfolio_small.optimize", lambda: _assert(bool(portfolio_small.optimize(method="min_vol")), "Portfolio.optimize vide"))
    report.run("portfolio_small.efficient_frontier", lambda: _not_empty_frame(portfolio_small.efficient_frontier(points=10), "Portfolio.efficient_frontier"))
    report.run("portfolio_small.backtest", lambda: _assert(bool(portfolio_small.backtest()), "Portfolio.backtest vide"))
    report.run("portfolio_small.sharpe", lambda: portfolio_small.sharpe())
    report.run("portfolio_small.plot", lambda: _assert(portfolio_small.plot() is not None, "Portfolio.plot None"))

    market_prices = portfolio_small.history(start="2026-01-01", end="2026-04-17")
    report.run("strategy.equal_weight", lambda: _assert(bool(bv.equal_weight_strategy(all_assets)({})), "equal_weight vide"))
    report.run("strategy.market_cap", lambda: _assert(bool(bv.market_cap_strategy(all_assets)({})), "market_cap_strategy vide"))
    report.run("strategy.momentum", lambda: _assert(bool(bv.momentum_strategy(lookback=20, top_n=3, symbols=all_assets)(market_prices)), "momentum_strategy vide"))
    report.run("strategy.value", lambda: _assert(isinstance(bv.value_strategy(top_n=3, symbols=all_assets)({}), dict), "value_strategy invalide"))
    report.run(
        "strategy.backtest_api",
        lambda: _assert(
            bool(
                bv.backtest(
                    bv.equal_weight_strategy(subset),
                    symbols=subset,
                    start="2026-01-01",
                    end="2026-04-17",
                )
            ),
            "api backtest vide",
        ),
    )


def main() -> int:
    report = ValidationReport()
    symbols = sorted(bv.list_assets())

    validate_global_api(report, symbols)
    validate_market_object(report, symbols)
    validate_index_object(report)

    for symbol in symbols:
        validate_symbol_surface(report, symbol)

    validate_portfolio_and_strategies(report, symbols)

    summary = {
        "assets": len(symbols),
        "passed": report.passed,
        "failed": report.failed,
        "failures": report.failures,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
