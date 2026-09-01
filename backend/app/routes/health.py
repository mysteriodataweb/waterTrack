from __future__ import annotations

import logging

from fastapi import APIRouter
from sqlalchemy import text

from ..database import engine
from ..schemas import HealthResponse
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


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
    external["groq"] = "ok" if settings.groq_api_key else "error"
    external["openrouteservice"] = "ok" if settings.openroute_api_key else "error"

    status = "ok" if db_ok == "ok" else "degraded"
    return HealthResponse(status=status, database=db_ok, external=external)
