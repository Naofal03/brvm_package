from datetime import date
from pydantic import BaseModel, Field

class Ticker(BaseModel):
    symbol: str = Field(..., description="Symbole de l'action à la BRVM, ex: SNTS")
    name: str = Field(..., description="Nom complet de l'entreprise")
    country: str | None = Field(default=None, description="Pays d'origine ou de base")
    sector: str | None = Field(default=None, description="Secteur d'activité")
    market_cap: float | None = Field(default=None, description="Capitalisation boursière (XOF)")

class DailyPrice(BaseModel):
    symbol: str = Field(..., description="Symbole de l'action")
    date: date = Field(..., description="Date de la cotation")
    open_price: float | None = Field(default=None, description="Prix d'ouverture (XOF)")
    close_price: float = Field(..., description="Prix de clôture (XOF)")
    high_price: float | None = Field(default=None, description="Plus haut du jour (XOF)")
    low_price: float | None = Field(default=None, description="Plus bas du jour (XOF)")
    volume: int | None = Field(default=None, description="Volume de titres échangés")
    value_traded: float | None = Field(default=None, description="Valeur totale échangée (XOF)")

class FundamentalData(BaseModel):
    symbol: str = Field(..., description="Symbole de l'action")
    year: int = Field(..., description="Année de l'exercice fiscal")
    net_income: float | None = Field(default=None, description="Résultat net de l'exercice (XOF)")
    per: float | None = Field(default=None, description="Price to Earnings Ratio (PER)")
    pbr: float | None = Field(default=None, description="Price to Book Ratio (PBR)")
    dividend_yield: float | None = Field(default=None, description="Rendement sur dividende (%)")
