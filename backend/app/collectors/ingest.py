"""
Ingestion incrémentale des dernières mesures NDWI pour les sources connues.

Permet une mise à jour quasi temps réel : re-collecte la période courante
depuis Sentinel-2 et insère/maj les observations en base.

Utilisé par :
  - le scheduler APScheduler (collecte hebdomadaire)
  - l'endpoint admin POST /api/admin/collect
"""
from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models import WaterSource, NdwiObservation
from .earth_engine import EarthEngineClient

logger = logging.getLogger(__name__)


def _current_period() -> tuple[str, str, str, str]:
    """Retourne (label, debut, fin, saison) de la période semestrielle en cours."""
    today = date.today()
    year = today.year
    if today.month >= 7:
        return (f"{year}-S2", f"{year}-07-01", f"{year}-12-31", "pluies")
    return (f"{year}-S1", f"{year}-01-01", f"{year}-06-30", "seche")


def collect_latest_period() -> int:
    """Collecte la période courante pour toutes les sources connues. Retourne n mesures insérées."""
    db = SessionLocal()
    client = EarthEngineClient()
    try:
        sources = db.execute(
            select(WaterSource).where(WaterSource.longitude.isnot(None))
        ).scalars().all()
        if not sources:
            logger.info("Aucune source connue : collecte ignorée.")
            return 0

        label, debut, fin, saison = _current_period()

        # Marquer la période actuelle comme existante avant insertion (upsert logique).
        existing = {
            (o.source_id, o.periode)
            for o in db.execute(
                select(NdwiObservation).where(NdwiObservation.periode == label)
            ).scalars()
        }

        payload = [
            {"longitude": s.longitude, "latitude": s.latitude}
            for s in sources
        ]
        rows = client.collect_period(debut, fin, label, saison, payload)

        inserted = 0
        for r in rows:
            # Retrouver la source par proximité GPS
            source = _nearest_source(db, sources, r["longitude"], r["latitude"])
            if source is None:
                continue
            if (source.id, label) in existing:
                continue
            obs = NdwiObservation(
                source_id=source.id,
                periode=label,
                observation_date=datetime.strptime(debut, "%Y-%m-%d").date(),
                saison=saison,
                ndwi=r["ndwi"],
                ndvi=r["ndvi"],
                satellite="sentinel-2",
            )
            db.add(obs)
            inserted += 1

        db.commit()
        logger.info("Collecte %s : %d mesures insérées.", label, inserted)
        return inserted
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Échec de la collecte périodique")
        raise
    finally:
        db.close()


def _nearest_source(db: Session, sources: list[WaterSource], lon: float, lat: float) -> WaterSource | None:
    """Trouve la source la plus proche d'un point GPS (fallback par distance)."""
    if not sources:
        return None
    best = None
    best_dist = float("inf")
    for s in sources:
        d = (s.longitude - lon) ** 2 + (s.latitude - lat) ** 2
        if d < best_dist:
            best_dist = d
            best = s
    return best


collect_weekly_job = collect_latest_period  # alias utilisé par le scheduler
