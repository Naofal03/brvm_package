"""
Ingest parsed financial data into the local database.
"""

def ingest_financial_data(company_code, year, data_dict, engine=None):
    """
    Store the parsed financial data in the database (FundamentalSnapshotORM).
    Args:
        company_code: str, code BRVM de la société
        year: int, année du snapshot
        data_dict: dict, champs financiers extraits
        engine: SQLAlchemy engine (optionnel, sinon auto)
    """
    from sqlalchemy.orm import Session
    from datetime import date
    from brvm_package.db.models import FundamentalSnapshotORM
    from sqlalchemy import create_engine

    if engine is None:
        engine = create_engine("sqlite:///brvm_data.db")

    snapshot_date = date(year, 12, 31)
    with Session(engine) as session:
        # Vérifie s'il existe déjà un snapshot pour ce symbol+date
        snap = session.query(FundamentalSnapshotORM).filter_by(symbol=company_code, snapshot_date=snapshot_date).first()
        if not snap:
            snap = FundamentalSnapshotORM(symbol=company_code, snapshot_date=snapshot_date)
        # Remplit les champs disponibles
        for k, v in data_dict.items():
            if hasattr(snap, k) and v is not None:
                setattr(snap, k, v)
        session.add(snap)
        session.commit()
