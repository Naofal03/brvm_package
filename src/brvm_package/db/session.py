from __future__ import annotations

import sqlite3

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from brvm_package.db.models import Base
from brvm_package.db.paths import ensure_database_path_ready, get_database_url

_DATABASE_URL: str | None = None
_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _database_url() -> str:
    global _DATABASE_URL
    if _DATABASE_URL is None:
        _DATABASE_URL = get_database_url()
    return _DATABASE_URL


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(_database_url(), future=True)
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


def AsyncSessionLocal() -> AsyncSession:
    return _get_session_factory()()

FUNDAMENTAL_SNAPSHOT_MIGRATIONS: dict[str, str] = {
    "pbr": "ALTER TABLE fundamental_snapshots ADD COLUMN pbr FLOAT",
    "roe": "ALTER TABLE fundamental_snapshots ADD COLUMN roe FLOAT",
    "market_cap": "ALTER TABLE fundamental_snapshots ADD COLUMN market_cap FLOAT",
    "shares_outstanding": "ALTER TABLE fundamental_snapshots ADD COLUMN shares_outstanding FLOAT",
    "float_ratio": "ALTER TABLE fundamental_snapshots ADD COLUMN float_ratio FLOAT",
    "beta_1y": "ALTER TABLE fundamental_snapshots ADD COLUMN beta_1y FLOAT",
    "major_shareholders": "ALTER TABLE fundamental_snapshots ADD COLUMN major_shareholders VARCHAR(2048)",
}


def _migrate_sqlite_schema() -> None:
    database_path = ensure_database_path_ready()
    with sqlite3.connect(database_path) as conn:
        columns = {
            str(row[1]).lower()
            for row in conn.execute("PRAGMA table_info(fundamental_snapshots)")
        }
        for column_name, ddl in FUNDAMENTAL_SNAPSHOT_MIGRATIONS.items():
            if column_name not in columns:
                conn.execute(ddl)
        conn.commit()


async def init_db() -> None:
    database_url = _database_url()
    if database_url.startswith("sqlite"):
        database_path = ensure_database_path_ready()
        database_path.parent.mkdir(parents=True, exist_ok=True)

    async with _get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if database_url.startswith("sqlite"):
        _migrate_sqlite_schema()
