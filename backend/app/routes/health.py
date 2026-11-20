from __future__ import annotations

import logging

from fastapi import APIRouter
from sqlalchemy import text

from ..database import SessionLocal, engine
from ..schemas import HealthResponse
from ..config import settings
from ..services import reservoirs as svc

logger = logging.getLogger(__name__)
router = APIRouter()


def data_freshness() -> dict:
    """Dernier mois de surfaces en base et retard : révèle une collecte mensuelle arrêtée."""
    from ..collectors.monthly import freshness   # import tardif : charge Earth Engine

    try:
        with SessionLocal() as db:
            return freshness(svc.latest_observed_month(db))
    except Exception:  # noqa: BLE001
        logger.exception("Health check : fraîcheur des données inconnue")
        return {"data": "unknown"}


@router.get("/health", response_model=HealthResponse)
def health():
    db_ok = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        logger.exception("Health check : base de données injoignable")
        db_ok = "error"

    external: dict[str, str] = {}
    external["openrouteservice"] = "ok" if settings.openroute_api_key else "error"

    data = data_freshness() if db_ok == "ok" else {"data": "unknown"}
    status = "ok" if db_ok == "ok" and data["data"] != "stale" else "degraded"
    return HealthResponse(status=status, database=db_ok, external=external, **data)
