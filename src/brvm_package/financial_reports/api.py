"""
API de haut niveau pour accéder aux états financiers stockés en base.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from brvm_package.db.paths import get_database_path


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = {key: row[key] for key in row.keys() if key not in {"id", "updated_at"}}
    snapshot_date = result.get("snapshot_date")
    if snapshot_date:
        result["fiscal_year"] = int(str(snapshot_date)[:4])
        result["fiscal_year_end"] = snapshot_date
    return result


def _annual_cutoff(as_of_date: str) -> str:
    parsed = date.fromisoformat(as_of_date)
    # Conservative annual-data policy: in year n, use the latest completed fiscal year n-1.
    return date(parsed.year - 1, 12, 31).isoformat()


def get_financials(
    symbol: str,
    fiscal_year: int | None = None,
    db_path: str | None = None,
    as_of_date: str | None = None,
) -> dict[str, Any] | None:
    """
    Retourne les états financiers d'une société.
    - `fiscal_year`: exercice comptable exact.
    - `as_of_date`: résolution conservative "année n -> derniers comptes annuels n-1".
    """
    target_path = db_path or str(get_database_path())

    with sqlite3.connect(target_path) as connection:
        connection.row_factory = sqlite3.Row
        if fiscal_year is not None:
            snapshot_date = date(fiscal_year, 12, 31).isoformat()
            row = connection.execute(
                """
                SELECT *
                FROM fundamental_snapshots
                WHERE UPPER(symbol) = UPPER(?)
                  AND snapshot_date = ?
                LIMIT 1
                """,
                (symbol, snapshot_date),
            ).fetchone()
        else:
            cutoff = _annual_cutoff(as_of_date) if as_of_date else None
            if cutoff is None:
                row = connection.execute(
                    """
                    SELECT *
                    FROM fundamental_snapshots
                    WHERE UPPER(symbol) = UPPER(?)
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                    """,
                    (symbol,),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT *
                    FROM fundamental_snapshots
                    WHERE UPPER(symbol) = UPPER(?)
                      AND snapshot_date <= ?
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                    """,
                    (symbol, cutoff),
                ).fetchone()

    if row is None:
        return None
    result = _row_to_dict(row)
    if as_of_date is not None:
        result["as_of_date"] = as_of_date
        result["selection_policy"] = "latest_completed_fiscal_year"
    return result


def get_financials_history(
    symbol: str,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """
    Retourne tous les exercices disponibles pour un symbole,
    avec les 15 indicateurs financiers clés, triés par année croissante.
    """
    target_path = db_path or str(get_database_path())
    with sqlite3.connect(target_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT *
            FROM fundamental_snapshots
            WHERE UPPER(symbol) = UPPER(?)
              AND snapshot_date LIKE '20__-12-31'
            ORDER BY snapshot_date ASC
            """,
            (symbol,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def list_available_years(symbol: str, db_path: str | None = None) -> list[int]:
    """
    Liste les années disponibles pour une société.
    """
    target_path = db_path or str(get_database_path())

    with sqlite3.connect(target_path) as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT CAST(substr(snapshot_date, 1, 4) AS INTEGER) AS report_year
            FROM fundamental_snapshots
            WHERE UPPER(symbol) = UPPER(?)
              AND snapshot_date LIKE '20__-12-31'
            ORDER BY report_year
            """,
            (symbol,),
        ).fetchall()

    return [int(row[0]) for row in rows if row[0] is not None]


def get_all_financials_db(
    db_path: str | None = None,
    symbols: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Retourne tous les snapshots annuels pour tous les symboles (ou une liste donnée).
    Utile pour construire des matrices d'analyse cross-entreprises.
    """
    target_path = db_path or str(get_database_path())
    with sqlite3.connect(target_path) as connection:
        connection.row_factory = sqlite3.Row
        if symbols:
            placeholders = ",".join("?" * len(symbols))
            rows = connection.execute(
                f"""
                SELECT *
                FROM fundamental_snapshots
                WHERE UPPER(symbol) IN ({placeholders})
                  AND snapshot_date LIKE '20__-12-31'
                ORDER BY symbol ASC, snapshot_date ASC
                """,
                [s.upper() for s in symbols],
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT *
                FROM fundamental_snapshots
                WHERE snapshot_date LIKE '20__-12-31'
                ORDER BY symbol ASC, snapshot_date ASC
                """,
            ).fetchall()
    return [_row_to_dict(row) for row in rows]
