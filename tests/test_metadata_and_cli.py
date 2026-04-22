from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import brvm as bv


def test_package_metadata_exposed() -> None:
    assert isinstance(bv.__version__, str)
    assert bv.__version__
    assert "download" in bv.__all__
    assert "Portfolio" in bv.__all__
    assert "list_stocks" in bv.__all__


def test_cli_version_command() -> None:
    typer = pytest.importorskip("typer.testing")
    from brvm_package.cli.main import app

    CliRunner = typer.CliRunner
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert bv.__version__ in result.stdout
