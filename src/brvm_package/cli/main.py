import asyncio
from datetime import date
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from brvm_package import __version__
from brvm_package.scraper.richbourse import RichbourseClient
from brvm_package.scraper.sikafinance import SikaFinanceClient
from brvm_package.services.sync import sync_market_data

app = typer.Typer(help="Application CLI pour extraire les données de la BRVM.")
console = Console()

def run_async(coro: Any) -> Any:
    return asyncio.run(coro)


def _parse_iso_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)

@app.command()
def richbourse():
    """Récupère les cotations générales depuis Richbourse."""
    console.print("[blue]Connexion à Richbourse...[/blue]")
    client = RichbourseClient()
    try:
        data = run_async(client.get_market_quotes())
        
        if not data:
            console.print("[yellow]Aucune donnée trouvée ou la structure du site a changé.[/yellow]")
            return

        table = Table("Symbole", "Prix", "Variation")
        for item in data:
            table.add_row(item.get("symbol", "-"), item.get("price", "-"), item.get("variation", "-"))
        
        console.print(table)
    except Exception as e:
        console.print(f"[red]Erreur de scraping Richbourse: {e}[/red]")


@app.command("version")
def version_command() -> None:
    """Affiche la version du package."""
    console.print(__version__)

@app.command()
def sikafinance(symbol: str = typer.Argument(..., help="Le symbole de l'action, ex: SNTS")):
    """Récupère le profil d'une action depuis SikaFinance."""
    console.print(f"[blue]Recherche du ticker {symbol.upper()} sur SikaFinance...[/blue]")
    client = SikaFinanceClient()
    try:
        data = run_async(client.get_ticker_info(symbol))
        console.print_json(data=data)
    except Exception as e:
        console.print(f"[red]Erreur de scraping SikaFinance: {e}[/red]")


@app.command("sync")
def sync_command(
    symbol: str | None = typer.Option(None, "--symbol", "-s", help="Symbole unique, ex: SNTS"),
    start: str | None = typer.Option(None, "--start", help="Date de début YYYY-MM-DD"),
    end: str | None = typer.Option(None, "--end", help="Date de fin YYYY-MM-DD"),
    concurrency: int = typer.Option(6, "--concurrency", "-c", help="Nombre maximum de synchronisations en parallèle."),
):
    """Synchronise la base SQLite et met à jour les nouvelles données quotidiennes."""
    try:
        start_date = _parse_iso_date(start)
        end_date = _parse_iso_date(end)
        result = run_async(
            sync_market_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                max_concurrency=concurrency,
            )
        )
        console.print_json(data=result)
    except Exception as e:
        console.print(f"[red]Erreur de synchronisation: {e}[/red]")

if __name__ == "__main__":
    app()
