"""
API de haut niveau pour accéder aux états financiers collectés via le package.
"""
from brvm_package.db.models import FundamentalSnapshotORM
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

def get_financials(symbol: str, year: int, engine=None):
    """
    Retourne un dict des états financiers pour une société et une année donnée.
    """
    if engine is None:
        engine = create_engine("sqlite:///brvm_data.db")
    with Session(engine) as session:
        snap = session.query(FundamentalSnapshotORM).filter_by(symbol=symbol, snapshot_date=f"{year}-12-31").first()
        if not snap:
            return None
        # Retourne tous les champs financiers sous forme de dict
        return {c.name: getattr(snap, c.name) for c in snap.__table__.columns if c.name not in ("id", "updated_at")}


def list_available_years(symbol: str, engine=None):
    """
    Liste les années pour lesquelles on a des états financiers pour une société.
    """
    if engine is None:
        engine = create_engine("sqlite:///brvm_data.db")
    with Session(engine) as session:
        snaps = session.query(FundamentalSnapshotORM).filter_by(symbol=symbol).all()
        return sorted({s.snapshot_date.year for s in snaps})
