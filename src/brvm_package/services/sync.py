from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert

from brvm_package.data import get_available_symbols
from brvm_package.data.catalog import get_asset_catalog
from brvm_package.db.models import DailyPriceORM, FundamentalSnapshotORM, TickerORM
from brvm_package.db.session import AsyncSessionLocal, init_db
from brvm_package.providers import DataRouter


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (float, int)):
        return float(value)

    text = str(value).strip().replace("\xa0", " ").replace(" ", "")
    text = text.replace("FCFA", "").replace("%", "").replace(",", ".")
    if text in {"", "-", "--", "N/A"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_int(value: Any) -> int | None:
    as_float = _to_float(value)
    if as_float is None:
        return None
    return int(as_float)


def _parse_sika_date(value: str) -> date:
    return datetime.strptime(value, "%d/%m/%Y").date()


async def _upsert_ticker_quotes(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    values: list[dict[str, Any]] = []
    for row in rows:
        symbol = str(row.get("symbol", "")).upper().strip()
        if not symbol:
            continue
        values.append(
            {
                "symbol": symbol,
                "source": str(row.get("source", "unknown")),
                "market_price": _to_float(row.get("price")),
                "variation": row.get("variation"),
            }
        )

    if not values:
        return 0

    async with AsyncSessionLocal() as session:
        stmt = insert(TickerORM).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol"],
            set_={
                "market_price": stmt.excluded.market_price,
                "variation": stmt.excluded.variation,
                "source": stmt.excluded.source,
                "updated_at": func.now(),
            },
        )
        await session.execute(stmt)
        await session.commit()

    return len(values)


async def _get_last_price_date(symbol: str) -> date | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.max(DailyPriceORM.date)).where(DailyPriceORM.symbol == symbol.upper())
        )
        return result.scalar_one_or_none()


async def _upsert_daily_prices(symbol: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    values: list[dict[str, Any]] = []
    for row in rows:
        if "Date" not in row:
            continue
        values.append(
            {
                "symbol": symbol.upper(),
                "date": _parse_sika_date(str(row["Date"])),
                "open_price": _to_float(row.get("Open")),
                "high_price": _to_float(row.get("High")),
                "low_price": _to_float(row.get("Low")),
                "close_price": _to_float(row.get("Close")) or 0.0,
                "volume": _to_int(row.get("Volume")),
                "source": str(row.get("source", "unknown")),
            }
        )

    if not values:
        return 0

    async with AsyncSessionLocal() as session:
        batch_size = 1000
        for i in range(0, len(values), batch_size):
            batch = values[i:i + batch_size]
            stmt = insert(DailyPriceORM).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "date"],
                set_={
                    "open_price": stmt.excluded.open_price,
                    "high_price": stmt.excluded.high_price,
                    "low_price": stmt.excluded.low_price,
                    "close_price": stmt.excluded.close_price,
                    "volume": stmt.excluded.volume,
                    "source": stmt.excluded.source,
                    "updated_at": func.now(),
                },
            )
            await session.execute(stmt)
        await session.commit()

    return len(values)


async def _upsert_fundamental_snapshot(symbol: str, info: dict[str, Any]) -> int:
    if not info:
        return 0

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
    if all(_to_float(info.get(field)) is None for field in meaningful_fields):
        return 0

    today = date.today()
    value = {
        "symbol": symbol.upper(),
        "snapshot_date": today,
        "revenue": _to_float(info.get("revenue")),
        "net_income": _to_float(info.get("net_income")),
        "eps": _to_float(info.get("eps")),
        "per": _to_float(info.get("per")),
        "pbr": _to_float(info.get("pbr")),
        "roe": _to_float(info.get("roe")),
        "dividend": _to_float(info.get("dividend")),
        "market_cap": _to_float(info.get("market_cap")),
        "shares_outstanding": _to_float(info.get("shares_outstanding")),
        "float_ratio": _to_float(info.get("float_ratio")),
        "beta_1y": _to_float(info.get("beta_1y")),
        "major_shareholders": info.get("major_shareholders"),
        "source": str(info.get("source", "unknown")),
    }

    async with AsyncSessionLocal() as session:
        stmt = insert(FundamentalSnapshotORM).values([value])
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "snapshot_date"],
            set_={
                "revenue": stmt.excluded.revenue,
                "net_income": stmt.excluded.net_income,
                "eps": stmt.excluded.eps,
                "per": stmt.excluded.per,
                "pbr": stmt.excluded.pbr,
                "roe": stmt.excluded.roe,
                "dividend": stmt.excluded.dividend,
                "market_cap": stmt.excluded.market_cap,
                "shares_outstanding": stmt.excluded.shares_outstanding,
                "float_ratio": stmt.excluded.float_ratio,
                "beta_1y": stmt.excluded.beta_1y,
                "major_shareholders": stmt.excluded.major_shareholders,
                "source": stmt.excluded.source,
                "updated_at": func.now(),
            },
        )
        await session.execute(stmt)
        await session.commit()
    return 1


async def sync_market_data(
    symbol: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    max_concurrency: int = 6,
) -> dict[str, Any]:
    await init_db()
    end = end_date or date.today()

    if symbol:
        symbols = [symbol.upper()]
        market_quotes: list[dict[str, Any]] = []
        market_attempts: list[dict[str, str]] = []
    else:
        router = DataRouter()
        market_result = await router.get_market_quotes()
        market_quotes = market_result.result.data
        market_attempts = market_result.attempts
        discovered_symbols = {
            str(row.get("symbol", "")).upper()
            for row in market_quotes
            if row.get("symbol")
        }
        symbols = sorted(discovered_symbols | set(get_asset_catalog()) | set(get_available_symbols()))
        if not discovered_symbols:
            market_attempts.append(
                {
                    "provider": "catalog",
                    "status": f"fallback: {len(symbols)} symboles connus utilises",
                }
            )

    tickers_synced = await _upsert_ticker_quotes(market_quotes)

    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def _sync_single_symbol(current_symbol: str) -> tuple[int, int, str, dict[str, Any]]:
        router = DataRouter()
        try:
            if start_date is not None:
                effective_start = start_date
            else:
                last_date = await _get_last_price_date(current_symbol)
                effective_start = (last_date + timedelta(days=1)) if last_date else date(2010, 1, 1)

            if effective_start > end:
                return 0, 0, current_symbol, {"history_rows": 0, "status": "up-to-date"}

            async with semaphore:
                history_result = await router.get_history(
                    current_symbol,
                    start_date=str(effective_start),
                    end_date=str(end),
                )
                history_rows = history_result.result.data
                fundamentals_result = await router.get_fundamentals(current_symbol)
                fundamental_info = fundamentals_result.result.data

            saved_rows = await _upsert_daily_prices(current_symbol, history_rows)
            saved_fundamentals = await _upsert_fundamental_snapshot(current_symbol, fundamental_info)

            details = {
                "history_rows": saved_rows,
                "from": str(effective_start),
                "to": str(end),
                "status": "ok",
                "history_source": history_result.result.provider,
                "fundamentals_source": fundamentals_result.result.provider,
                "history_attempts": history_result.attempts,
                "fundamentals_attempts": fundamentals_result.attempts,
            }
            return saved_rows, saved_fundamentals, current_symbol, details
        except Exception as exc:  # noqa: BLE001
            return 0, 0, current_symbol, {"history_rows": 0, "status": f"error: {exc}"}

    results = await asyncio.gather(*(_sync_single_symbol(current_symbol) for current_symbol in symbols))
    history_fetched = sum(item[0] for item in results)
    fundamentals_saved = sum(item[1] for item in results)
    per_symbol = {symbol_key: details for _, _, symbol_key, details in results}

    return {
        "symbols": len(symbols),
        "tickers_synced": tickers_synced,
        "history_rows_upserted": history_fetched,
        "fundamental_snapshots_saved": fundamentals_saved,
        "max_concurrency": max(1, max_concurrency),
        "market_attempts": market_attempts,
        "details": per_symbol,
    }
