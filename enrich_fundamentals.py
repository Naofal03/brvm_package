"""Enrichit la base brvm.sqlite3 avec les données manquantes depuis SikaFinance."""

import asyncio
import sqlite3
import shutil

from brvm_package.scraper.sikafinance import SikaFinanceClient
from brvm_package.data.catalog import get_asset_catalog

DB = "data/brvm.sqlite3"


async def enrich_all():
    client = SikaFinanceClient()
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    symbols = sorted(get_asset_catalog().keys())
    enriched = 0

    for symbol in symbols:
        try:
            info = await client.get_ticker_info(symbol)
            if not info:
                print(f"  ⚠️  {symbol}: pas de données SikaFinance")
                continue

            # Extract values
            pbr = info.get("pbr")
            roe = info.get("roe")
            float_ratio = info.get("float_ratio")
            beta_1y = info.get("beta_1y")
            major_shareholders = info.get("major_shareholders")

            # Only update the LATEST snapshot (SikaFinance daily data), preserve BRVM data
            c.execute(
                """
                UPDATE fundamental_snapshots 
                SET pbr = COALESCE(?, pbr),
                    roe = COALESCE(?, roe),
                    float_ratio = COALESCE(?, float_ratio),
                    beta_1y = COALESCE(?, beta_1y),
                    major_shareholders = COALESCE(?, major_shareholders)
                WHERE symbol = ?
                AND snapshot_date = (
                    SELECT MAX(snapshot_date) FROM fundamental_snapshots WHERE symbol = ?
                )
            """,
                (pbr, roe, float_ratio, beta_1y, major_shareholders, symbol, symbol),
            )

            if c.rowcount > 0:
                enriched += 1
                print(
                    f"  ✅ {symbol}: pbr={pbr}, roe={roe}, float={float_ratio}, beta={beta_1y}"
                )
            else:
                print(f"  ⚠️  {symbol}: pas de snapshot dans la base")

        except Exception as e:
            print(f"  ❌ {symbol}: erreur - {e}")

    conn.commit()

    # Verify final state
    print("\n=== Vérification finale ===")
    c.execute(
        """
        SELECT 
            SUM(CASE WHEN pbr IS NULL THEN 1 ELSE 0 END),
            SUM(CASE WHEN roe IS NULL THEN 1 ELSE 0 END),
            SUM(CASE WHEN float_ratio IS NULL THEN 1 ELSE 0 END),
            SUM(CASE WHEN beta_1y IS NULL THEN 1 ELSE 0 END),
            SUM(CASE WHEN major_shareholders IS NULL THEN 1 ELSE 0 END)
        FROM fundamental_snapshots
    """
    )
    pbr_null, roe_null, fr_null, beta_null, ms_null = c.fetchone()
    total = c.execute("SELECT COUNT(*) FROM fundamental_snapshots").fetchone()[0]
    print(f"pbr NULL: {pbr_null}/{total}")
    print(f"roe NULL: {roe_null}/{total}")
    print(f"float_ratio NULL: {fr_null}/{total}")
    print(f"beta_1y NULL: {beta_null}/{total}")
    print(f"major_shareholders NULL: {ms_null}/{total}")

    conn.close()

    # Sync back to resources
    shutil.copy2(DB, "src/brvm_package/resources/brvm.sqlite3")
    print(f"\n✅ {enriched} tickers enrichis depuis SikaFinance")
    print("   Base synchronisée vers src/brvm_package/resources/brvm.sqlite3")


if __name__ == "__main__":
    asyncio.run(enrich_all())
