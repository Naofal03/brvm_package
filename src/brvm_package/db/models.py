from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TickerORM(Base):
    __tablename__ = "tickers"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), default="richbourse")
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    market_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    variation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
    )


class DailyPriceORM(Base):
    __tablename__ = "daily_prices"
    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_daily_prices_symbol_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    open_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    high_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    low_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    close_price: Mapped[float] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="sikafinance")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
    )


class FundamentalSnapshotORM(Base):
    __tablename__ = "fundamental_snapshots"
    __table_args__ = (UniqueConstraint("symbol", "snapshot_date", name="uix_symbol_date_snap"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    revenue: Mapped[float | None] = mapped_column(Float, nullable=True) # Chiffre d'affaires
    operating_income: Mapped[float | None] = mapped_column(Float, nullable=True) # Résultat opérationnel
    net_income: Mapped[float | None] = mapped_column(Float, nullable=True) # Résultat net
    equity: Mapped[float | None] = mapped_column(Float, nullable=True) # Capitaux propres
    total_assets: Mapped[float | None] = mapped_column(Float, nullable=True) # Total actif
    total_liabilities: Mapped[float | None] = mapped_column(Float, nullable=True) # Dettes totales
    current_assets: Mapped[float | None] = mapped_column(Float, nullable=True) # Actifs courants
    current_liabilities: Mapped[float | None] = mapped_column(Float, nullable=True) # Passifs courants
    operating_margin: Mapped[float | None] = mapped_column(Float, nullable=True) # Marge opérationnelle
    net_margin: Mapped[float | None] = mapped_column(Float, nullable=True) # Marge nette
    roe: Mapped[float | None] = mapped_column(Float, nullable=True) # Return on Equity
    roa: Mapped[float | None] = mapped_column(Float, nullable=True) # Return on Assets
    debt_ratio: Mapped[float | None] = mapped_column(Float, nullable=True) # Ratio d'endettement
    equity_ratio: Mapped[float | None] = mapped_column(Float, nullable=True) # Autonomie financière
    current_ratio: Mapped[float | None] = mapped_column(Float, nullable=True) # Ratio de liquidité générale
    eps: Mapped[float | None] = mapped_column(Float, nullable=True) # BNPA
    per: Mapped[float | None] = mapped_column(Float, nullable=True)
    pbr: Mapped[float | None] = mapped_column(Float, nullable=True)
    dividend: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    shares_outstanding: Mapped[float | None] = mapped_column(Float, nullable=True)
    float_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    beta_1y: Mapped[float | None] = mapped_column(Float, nullable=True)
    major_shareholders: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="sikafinance")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
    )
