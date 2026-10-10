from __future__ import annotations

import ssl

from sqlalchemy import URL, create_engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings
from .tls import use_system_certificates


class Base(DeclarativeBase):
    pass


def _normalize_url(url: str) -> tuple[URL, dict]:
    """Force le driver pg8000 et traduit les options libpq qu'il ne connaît pas.

    Les hébergeurs (Neon, Render...) fournissent une URL pour libpq, du type
    `postgresql://...?sslmode=require&channel_binding=require`. pg8000 refuse ces
    paramètres : `sslmode` devient un contexte TLS, `channel_binding` est retiré
    (pg8000 le négocie seul dès que la connexion est chiffrée).
    """
    url = url.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+pg8000://", 1)
    if not url.startswith("postgresql+pg8000://"):
        raise RuntimeError(
            "DATABASE_URL doit être une URL PostgreSQL (postgresql+pg8000://...)"
        )
    parsed = make_url(url)
    sslmode = parsed.query.get("sslmode")
    parsed = parsed.difference_update_query(["sslmode", "channel_binding"])

    connect_args: dict = {}
    if sslmode and sslmode != "disable":
        use_system_certificates()
        connect_args["ssl_context"] = ssl.create_default_context()
    return parsed, connect_args


DATABASE_URL, _CONNECT_ARGS = _normalize_url(settings.database_url)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_CONNECT_ARGS)

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
    import importlib

    # L'import enregistre les tables (v2 et v3) sur Base.metadata
    importlib.import_module(f"{__package__}.models")
    ensure_postgis()
    Base.metadata.create_all(bind=engine)
