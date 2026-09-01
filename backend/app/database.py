from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.dialects import postgresql

from .config import settings


class Base(DeclarativeBase):
    pass


def _normalize_url(url: str) -> str:
    """Force le driver pg8000 et le dialecte postgresql."""
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+pg8000://", 1)
    if not url.startswith("postgresql+pg8000://"):
        raise RuntimeError(
            "DATABASE_URL doit être une URL PostgreSQL (postgresql+pg8000://...)"
        )
    return url


DATABASE_URL = _normalize_url(settings.database_url)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Réutilisé par les scripts/collectors pour créer les tables PostGIS.
def ensure_postgis() -> None:
    """Active l'extension PostGIS si besoin (idempotent)."""
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))


def create_all() -> None:
    from . import models  # noqa: F401  (enregistre les modèles sur Base)

    ensure_postgis()
    Base.metadata.create_all(bind=engine)
