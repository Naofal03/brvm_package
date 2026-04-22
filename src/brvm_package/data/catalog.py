from __future__ import annotations

from typing import Any

COUNTRY_TO_SIKA_SUFFIX: dict[str, str] = {
    "Benin": "bj",
    "Burkina Faso": "bf",
    "Cote d'Ivoire": "ci",
    "Mali": "ml",
    "Niger": "ne",
    "Senegal": "sn",
    "Togo": "tg",
}

ASSET_CATALOG: dict[str, dict[str, str]] = {
    "ABJC": {"name": "Servair Abidjan Cote d'Ivoire", "sector": "Distribution", "country": "Cote d'Ivoire"},
    "BICB": {"name": "Banque Internationale Pour l'Industrie et le Commerce du Benin", "sector": "Services Financiers", "country": "Benin"},
    "BICC": {"name": "BICI Cote d'Ivoire", "sector": "Services Financiers", "country": "Cote d'Ivoire"},
    "BNBC": {"name": "Bernabe Cote d'Ivoire", "sector": "Distribution", "country": "Cote d'Ivoire"},
    "BOAB": {"name": "Bank of Africa Benin", "sector": "Services Financiers", "country": "Benin"},
    "BOABF": {"name": "Bank of Africa Burkina Faso", "sector": "Services Financiers", "country": "Burkina Faso"},
    "BOAC": {"name": "Bank of Africa Cote d'Ivoire", "sector": "Services Financiers", "country": "Cote d'Ivoire"},
    "BOAM": {"name": "Bank of Africa Mali", "sector": "Services Financiers", "country": "Mali"},
    "BOAN": {"name": "Bank of Africa Niger", "sector": "Services Financiers", "country": "Niger"},
    "BOAS": {"name": "Bank of Africa Senegal", "sector": "Services Financiers", "country": "Senegal"},
    "CABC": {"name": "Sicable Cote d'Ivoire", "sector": "Industriels", "country": "Cote d'Ivoire"},
    "CBIBF": {"name": "Coris Bank International Burkina Faso", "sector": "Services Financiers", "country": "Burkina Faso"},
    "CFAC": {"name": "CFAO Motors Cote d'Ivoire", "sector": "Distribution", "country": "Cote d'Ivoire"},
    "CIEC": {"name": "CIE Cote d'Ivoire", "sector": "Services Publics", "country": "Cote d'Ivoire"},
    "ECOC": {"name": "Ecobank Cote d'Ivoire", "sector": "Services Financiers", "country": "Cote d'Ivoire"},
    "ETIT": {"name": "Ecobank Transnational Incorporated", "sector": "Services Financiers", "country": "Togo"},
    "FTSC": {"name": "Filtisac Cote d'Ivoire", "sector": "Industriels", "country": "Cote d'Ivoire"},
    "LNBB": {"name": "Loterie Nationale du Benin", "sector": "Distribution", "country": "Benin"},
    "NEIC": {"name": "NEI-CEDA Cote d'Ivoire", "sector": "Distribution", "country": "Cote d'Ivoire"},
    "NSBC": {"name": "NSIA Banque Cote d'Ivoire", "sector": "Services Financiers", "country": "Cote d'Ivoire"},
    "NTLC": {"name": "Nestle Cote d'Ivoire", "sector": "Consommation de Base", "country": "Cote d'Ivoire"},
    "ONTBF": {"name": "Onatel Burkina Faso", "sector": "Télécommunications", "country": "Burkina Faso"},
    "ORAC": {"name": "Orange Cote d'Ivoire", "sector": "Télécommunications", "country": "Cote d'Ivoire"},
    "ORGT": {"name": "Oragroup Togo", "sector": "Services Financiers", "country": "Togo"},
    "PALC": {"name": "Palm Cote d'Ivoire", "sector": "Consommation de Base", "country": "Cote d'Ivoire"},
    "PRSC": {"name": "Tractafric Motors Cote d'Ivoire", "sector": "Distribution", "country": "Cote d'Ivoire"},
    "SAFC": {"name": "Safca Cote d'Ivoire", "sector": "Consommation de Base", "country": "Cote d'Ivoire"},
    "SCRC": {"name": "Sucrivoire Cote d'Ivoire", "sector": "Consommation de Base", "country": "Cote d'Ivoire"},
    "SDCC": {"name": "Sode Cote d'Ivoire", "sector": "Services Publics", "country": "Cote d'Ivoire"},
    "SDSC": {"name": "Africa Global Logistics Cote d'Ivoire", "sector": "Transport", "country": "Cote d'Ivoire"},
    "SEMC": {"name": "Eviosys Packaging Siem Cote d'Ivoire", "sector": "Industriels", "country": "Cote d'Ivoire"},
    "SGBC": {"name": "Societe Generale Cote d'Ivoire", "sector": "Services Financiers", "country": "Cote d'Ivoire"},
    "SHEC": {"name": "Vivo Energy Cote d'Ivoire", "sector": "Distribution", "country": "Cote d'Ivoire"},
    "SIBC": {"name": "Societe Ivoirienne de Banque Cote d'Ivoire", "sector": "Services Financiers", "country": "Cote d'Ivoire"},
    "SICC": {"name": "Sicor Cote d'Ivoire", "sector": "Consommation de Base", "country": "Cote d'Ivoire"},
    "SIVC": {"name": "Erium Cote d'Ivoire", "sector": "Industriels", "country": "Cote d'Ivoire"},
    "SLBC": {"name": "Solibra Cote d'Ivoire", "sector": "Consommation de Base", "country": "Cote d'Ivoire"},
    "SMBC": {"name": "SMB Cote d'Ivoire", "sector": "Consommation de Base", "country": "Cote d'Ivoire"},
    "SNTS": {"name": "Sonatel Senegal", "sector": "Télécommunications", "country": "Senegal"},
    "SOGC": {"name": "SOGB Cote d'Ivoire", "sector": "Agriculture", "country": "Cote d'Ivoire"},
    "SPHC": {"name": "SAPH Cote d'Ivoire", "sector": "Agriculture", "country": "Cote d'Ivoire"},
    "STAC": {"name": "Setao Cote d'Ivoire", "sector": "Industriels", "country": "Cote d'Ivoire"},
    "STBC": {"name": "Sitab Cote d'Ivoire", "sector": "Consommation de Base", "country": "Cote d'Ivoire"},
    "TTLC": {"name": "TotalEnergies Marketing Cote d'Ivoire", "sector": "Distribution", "country": "Cote d'Ivoire"},
    "TTLS": {"name": "TotalEnergies Marketing Senegal", "sector": "Distribution", "country": "Senegal"},
    "UNLC": {"name": "Unilever Cote d'Ivoire", "sector": "Consommation de Base", "country": "Cote d'Ivoire"},
    "UNXC": {"name": "Uniwax Cote d'Ivoire", "sector": "Consommation Discrétionnaire", "country": "Cote d'Ivoire"},
}

SIKA_TICKER_OVERRIDES: dict[str, str] = {
    "BRVMC": "BRVMC",
    "BRVM30": "BRVM30",
    "BRVM10": "BRVM10",
}

SECTOR_ALIASES: dict[str, str] = {
    "agriculture": "Agriculture",
    "banking": "Services Financiers",
    "consumer staples": "Consommation de Base",
    "consumer discretionary": "Consommation Discrétionnaire",
    "distribution": "Distribution",
    "energy": "Energie",
    "energie": "Energie",
    "industrials": "Industriels",
    "industriels": "Industriels",
    "services financiers": "Services Financiers",
    "financial services": "Services Financiers",
    "utilities": "Services Publics",
    "services publics": "Services Publics",
    "telecommunications": "Télécommunications",
    "telecommunicationss": "Télécommunications",
    "télécommunications": "Télécommunications",
    "transport": "Transport",
}

INDEX_RECORDS: list[dict[str, str]] = [
    {"symbol": "BRVM-30", "name": "BRVM-30", "category": "Benchmark"},
    {"symbol": "BRVM-C", "name": "BRVM - COMPOSITE", "category": "Benchmark"},
    {"symbol": "BRVM-PRES", "name": "BRVM - PRESTIGE", "category": "Benchmark"},
    {"symbol": "BRVM-PRINC", "name": "BRVM - PRINCIPAL", "category": "Benchmark"},
    {"symbol": "BRVM-CB", "name": "BRVM - CONSOMMATION DE BASE", "category": "Sector"},
    {"symbol": "BRVM-CD", "name": "BRVM - CONSOMMATION DISCRETIONNAIRE", "category": "Sector"},
    {"symbol": "BRVM-ENER", "name": "BRVM - ENERGIE", "category": "Sector"},
    {"symbol": "BRVM-IND", "name": "BRVM - INDUSTRIELS", "category": "Sector"},
    {"symbol": "BRVM-FIN", "name": "BRVM - SERVICES FINANCIERS", "category": "Sector"},
    {"symbol": "BRVM-UTIL", "name": "BRVM - SERVICES PUBLICS", "category": "Sector"},
    {"symbol": "BRVM-TEL", "name": "BRVM - TELECOMMUNICATIONS", "category": "Sector"},
    {"symbol": "BRVM-CTR", "name": "BRVM - COMPOSITE TOTAL RETURN", "category": "Total Return"},
]


def get_asset_catalog() -> dict[str, dict[str, str]]:
    return ASSET_CATALOG


def get_asset_metadata(symbol: str) -> dict[str, str]:
    return ASSET_CATALOG.get(symbol.upper(), {}).copy()


def get_asset_records() -> list[dict[str, str]]:
    return [{"symbol": symbol, **metadata} for symbol, metadata in ASSET_CATALOG.items()]


def get_index_records() -> list[dict[str, str]]:
    return [record.copy() for record in INDEX_RECORDS]


def get_sector_names() -> list[str]:
    return sorted({item["sector"] for item in ASSET_CATALOG.values()})


def normalize_sector_name(value: str) -> str:
    normalized = value.strip().lower()
    return SECTOR_ALIASES.get(normalized, value.strip())


def get_country_names() -> list[str]:
    return sorted({item["country"] for item in ASSET_CATALOG.values()})


def get_sika_ticker(symbol: str) -> str:
    normalized_symbol = symbol.upper()
    if normalized_symbol in SIKA_TICKER_OVERRIDES:
        return SIKA_TICKER_OVERRIDES[normalized_symbol]

    metadata = get_asset_metadata(normalized_symbol)
    country = metadata.get("country")
    if country is None:
        return f"{normalized_symbol}.ci"

    suffix = COUNTRY_TO_SIKA_SUFFIX.get(country)
    if suffix is None:
        return f"{normalized_symbol}.ci"
    return f"{normalized_symbol}.{suffix}"


def merge_asset_metadata(symbol: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    merged: dict[str, Any] = {"symbol": symbol.upper(), **get_asset_metadata(symbol)}
    if extra:
        merged.update(extra)
    return merged
