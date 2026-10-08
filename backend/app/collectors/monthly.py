"""
Mise à jour mensuelle v3 : collecte satellite du dernier mois, prévisions, statuts.

Étapes (idempotentes, rejouables) :
  1. dernier mois disponible (ERA5-Land et CHIRPS sont publiés avec retard) ;
  2. surface en eau 10 m + forçages climatiques de chaque réservoir modélisable ;
  3. prévisions 1-3 mois avec le paquet `ml/runs/forecast_latest/bundle.joblib` ;
  4. report de la prévision à 1 mois sur les sources de l'application (carte).

Déclenchée par le scheduler (si activé) ou par `POST /api/admin/monthly-update`.
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
from sqlalchemy import select

from ..config import settings
from ..database import SessionLocal
from ..models import Reservoir, WaterAreaObservation
from ..services import reservoirs as svc
from .earth_engine import EarthEngineClient
from .water_area import collect_month, last_available_month

logger = logging.getLogger(__name__)


def _model_version(bundle: dict) -> str:
    return f"{bundle.get('version')} ({bundle.get('created')})"


def forecast_and_publish(db, bundle: dict, issue_month: Optional[str] = None) -> dict:
    """Prévisions à partir du panel en base, puis mise à jour des statuts des sources."""
    from ml.forecasting import forecast

    panel = svc.load_panel(db)
    if panel.empty:
        raise RuntimeError("Aucune observation v3 en base : exécuter scripts/load_v3.py")
    issue = pd.Timestamp(issue_month) if issue_month else panel["date"].max()
    fc = forecast(bundle, panel, issue=issue)
    n_fc = svc.upsert_forecasts(db, fc, _model_version(bundle))
    n_src = svc.apply_forecasts_to_sources(db, issue.date())
    return {"issue_month": issue.strftime("%Y-%m"), "forecasts": n_fc, "sources_updated": n_src,
            "status_counts": fc[fc["horizon"] == 1]["status"].value_counts().to_dict()}


def run_monthly_update(month: Optional[str] = None, force: bool = False) -> dict:
    from ml.forecasting import load_bundle

    bundle = load_bundle()
    if abs(bundle["critical_fill"] - settings.critical_fill) > 1e-9:
        logger.warning("CRITICAL_FILL (%.2f) différent du seuil d'entraînement du modèle (%.2f)",
                       settings.critical_fill, bundle["critical_fill"])

    EarthEngineClient().initialize()
    month = month or last_available_month()
    db = SessionLocal()
    try:
        already = db.execute(
            select(WaterAreaObservation.id).where(
                WaterAreaObservation.month == pd.Period(month, "M").to_timestamp().date()
            ).limit(1)
        ).first()
        collected = 0
        if already and not force:
            logger.info("Mois %s déjà collecté : collecte ignorée", month)
        else:
            regions = svc.region_geojson(db)
            hybas = dict(db.execute(select(Reservoir.id, Reservoir.hybas_id).where(Reservoir.modelable)).all())
            logger.info("Collecte v3 %s : %d réservoirs", month, len(regions))
            df = collect_month(month, regions, hybas, bundle)
            collected = svc.upsert_observations(db, df)
            db.commit()

        summary = forecast_and_publish(db, bundle, month)
        db.commit()
        summary["collected"] = collected
        logger.info("Mise à jour mensuelle : %s", summary)
        return summary
    except Exception:
        db.rollback()
        logger.exception("Échec de la mise à jour mensuelle")
        raise
    finally:
        db.close()
