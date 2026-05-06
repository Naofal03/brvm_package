"""
CLI pour collecter et interroger les états financiers BRVM.
"""
import asyncio

import typer

from brvm_package.financial_reports.collect_pipeline import collect_all
from brvm_package.financial_reports.api import get_financials, list_available_years

app = typer.Typer()

@app.command()
def collect():
    """Lance la collecte complète des états financiers (2020–2025)."""
    typer.echo(asyncio.run(collect_all()))

@app.command()
def show(symbol: str, year: int | None = None, as_of_date: str | None = None):
    """Affiche les états financiers d'une société pour un exercice ou à une date donnée."""
    data = get_financials(symbol, fiscal_year=year, as_of_date=as_of_date)
    if not data:
        if year is not None:
            typer.echo(f"Aucune donnée pour {symbol} sur l'exercice {year}")
        else:
            typer.echo(f"Aucune donnée pour {symbol}")
    else:
        for k, v in data.items():
            typer.echo(f"{k}: {v}")

@app.command()
def years(symbol: str):
    """Liste les années disponibles pour une société."""
    y = list_available_years(symbol)
    typer.echo(f"Années disponibles pour {symbol}: {y}")

if __name__ == "__main__":
    app()
