from __future__ import annotations

import os
import shutil
from pathlib import Path
from urllib.parse import unquote, urlparse

from importlib import resources

PACKAGE_NAME = "brvm_package"
DATABASE_FILENAME = "brvm.sqlite3"
DEFAULT_USER_DB_PATH = Path.home() / ".brvm" / DATABASE_FILENAME


def get_database_path() -> Path:
    explicit_path = _path_from_environment()
    if explicit_path is not None:
        explicit_path.parent.mkdir(parents=True, exist_ok=True)
        _seed_database_if_needed(explicit_path)
        return explicit_path

    source_tree_path = _source_tree_database_path()
    if source_tree_path is not None:
        return source_tree_path

    target_path = DEFAULT_USER_DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    _seed_database_if_needed(target_path)
    return target_path


def get_database_url() -> str:
    explicit_url = os.getenv("BRVM_DATABASE_URL")
    if explicit_url:
        return explicit_url
    return f"sqlite+aiosqlite:///{get_database_path()}"


def ensure_database_path_ready() -> Path:
    database_path = get_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    if not database_path.exists():
        _seed_database_if_needed(database_path)
    return database_path


def _path_from_environment() -> Path | None:
    explicit_url = os.getenv("BRVM_DATABASE_URL")
    if explicit_url:
        parsed_from_url = _sqlite_path_from_url(explicit_url)
        if parsed_from_url is not None:
            return parsed_from_url

    explicit_path = os.getenv("BRVM_DATABASE_PATH")
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()

    return None


def _sqlite_path_from_url(url: str) -> Path | None:
    if not url.startswith("sqlite"):
        return None

    parsed = urlparse(url)
    raw_path = unquote(parsed.path or "")
    if not raw_path:
        return None

    return Path(raw_path).expanduser().resolve()


def _source_tree_database_path() -> Path | None:
    project_root = Path(__file__).resolve().parents[3]
    candidate = project_root / "data" / DATABASE_FILENAME
    if candidate.exists():
        return candidate
    return None


def _seed_database_if_needed(target_path: Path) -> None:
    if target_path.exists():
        return

    seed_path = _seed_database_path()
    if seed_path is None:
        return

    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed_path, target_path)


def _seed_database_path() -> Path | None:
    source_tree_path = _source_tree_database_path()
    if source_tree_path is not None:
        return source_tree_path

    try:
        traversable = resources.files(PACKAGE_NAME).joinpath("resources", DATABASE_FILENAME)
        if not traversable.is_file():
            return None
        with resources.as_file(traversable) as resource_path:
            return Path(resource_path)
    except (FileNotFoundError, ModuleNotFoundError):
        return None
