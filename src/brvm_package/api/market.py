import pandas as pd
from typing import Any, List

from brvm_package.data import (
    get_asset_info,
    get_available_symbols,
    get_country_names,
    get_market_summary as load_market_summary,
    get_sector_names,
    search_assets,
)
from brvm_package.data.catalog import get_index_records

def list_assets() -> List[str]:
    """Retourne la liste des symboles disponibles localement."""
    return get_available_symbols()


def list_stocks() -> List[str]:
    """Alias orienté utilisateur de list_assets()."""
    return list_assets()

def list_indices(detailed: bool = False) -> List[str] | pd.DataFrame:
    """Retourne les indices BRVM connus, avec option détaillée par catégorie."""
    records = get_index_records()
    if detailed:
        return pd.DataFrame(records)
    return [record["name"] for record in records]

def list_sectors() -> List[str]:
    """Liste les secteurs connus du catalogue BRVM."""
    return get_sector_names()


def list_countries() -> List[str]:
    """Liste les pays connus du catalogue BRVM."""
    return get_country_names()


def market_summary() -> dict[str, Any]:
    """Retourne un résumé du dernier jour de marché disponible dans la base locale."""
    return load_market_summary()


def asset_info(symbol: str) -> dict[str, Any]:
    """Retourne la fiche synthétique d'un actif."""
    return get_asset_info(symbol)


def search(query: str) -> pd.DataFrame:
    """Recherche simple sur symbole, nom, secteur ou pays."""
    return search_assets(query)


def get_market():
    """Retourne un objet Market orienté utilisateur."""
    from brvm_package.objects.market import Market

    return Market()
