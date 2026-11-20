"""
Mise à jour mensuelle v3 : collecte satellite, prévisions, statuts.

Étapes (idempotentes, rejouables) :
  1. dernier mois disponible (ERA5-Land et CHIRPS sont publiés avec retard) ;
  2. rattrapage : chaque mois manquant depuis le dernier mois en base, du plus
     ancien au plus récent (au plus `MAX_CATCH_UP` par passage), est collecté
     puis enregistré aussitôt : un échec sur un mois ne fait pas perdre les précédents ;
  3. surface en eau 10 m + forçages climatiques de chaque réservoir modélisable,
     avec un contrôle de qualité (part des retenues sans mesure) ;
  4. pour chaque mois collecté : prévisions 1-3 mois avec le paquet
     `ml/runs/forecast_latest/bundle.joblib`, report de la prévision à 1 mois sur les
     sources de l'application (carte) et, d'octobre à mars, mois prévu de passage sous
     le niveau critique (`ml/drying.py`) ;
  5. vérification des prévisions émises plus tôt pour les mois collectés (`ml/verification.py`) ;
  6. fraîcheur : retard du dernier mois en base sur le dernier mois complet.

Déclenchée par un planificateur externe (`scripts/monthly_update.py`, workflow
GitHub Actions), par le scheduler interne (si activé) ou par `POST /api/admin/monthly-update`.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

import pandas as pd

from ..config import settings
from ..database import SessionLocal
from ..services import reservoirs as svc
from .earth_engine import EarthEngineClient
from .water_area import collect_month, last_available_month

logger = logging.getLogger(__name__)

MAX_CATCH_UP = 6          # mois collectés au plus par passage (3 requêtes Earth Engine par mois)
MAX_MISSING_SHARE = 0.25  # au-delà, le mois est signalé : nuages persistants ou radar inutilisable
STALE_AFTER_MONTHS = 2    # retard normal : 0 à 2 mois (CHIRPS est publié environ trois semaines après le mois)


def _model_version(bundle: dict) -> str:
    return f"{bundle.get('version')} ({bundle.get('created')})"


# --------------------------------------------------------------------------- #
# Planification et contrôles
# --------------------------------------------------------------------------- #
def plan_months(latest_observed: Optional[date], last_available: str,
                max_months: int = MAX_CATCH_UP) -> tuple[list[str], int]:
    """Mois à collecter, du plus ancien au plus récent, et nombre de mois reportés au passage suivant."""
    if latest_observed is None:
        raise RuntimeError("Aucune observation v3 en base : exécuter scripts/load_v3.py")
    start = pd.Period(latest_observed, "M") + 1
    last = pd.Period(last_available, "M")
    months = [str(p) for p in pd.period_range(start, last, freq="M")] if start <= last else []
    return months[:max_months], max(0, len(months) - max_months)


def months_behind(latest_observed: Optional[date], today: Optional[date] = None) -> Optional[int]:
    """Mois écoulés entre le dernier mois en base et le dernier mois complet (None si la base est vide)."""
    if latest_observed is None:
        return None
    last_complete = pd.Period(today or date.today(), "M") - 1
    return max(0, (last_complete - pd.Period(latest_observed, "M")).n)


def freshness(latest_observed: Optional[date], today: Optional[date] = None) -> dict:
    """État des données pour la surveillance : `ok`, `stale` (en retard) ou `empty`."""
    behind = months_behind(latest_observed, today)
    state = "empty" if behind is None else ("stale" if behind > STALE_AFTER_MONTHS else "ok")
    return {"latest_month": latest_observed.strftime("%Y-%m") if latest_observed else None,
            "months_behind": behind, "data": state}


def quality_warnings(df: pd.DataFrame, month: str) -> list[str]:
    """Signale un mois mal mesuré, sans bloquer la mise à jour."""
    if df.empty:
        return [f"{month} : aucune retenue mesurée"]
    out = []
    missing = (df["area_source"] == "manquant").mean()
    if missing > MAX_MISSING_SHARE:
        out.append(f"{month} : {missing:.0%} des retenues sans mesure (nuages persistants, radar inutilisable)")
    no_climate = df[["precip_mm", "pet_mm"]].isna().all(axis=1).mean()
    if no_climate > MAX_MISSING_SHARE:
        out.append(f"{month} : {no_climate:.0%} des retenues sans forçages climatiques (CHIRPS, ERA5-Land)")
    return out


# --------------------------------------------------------------------------- #
# Mise à jour
# --------------------------------------------------------------------------- #
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
            "status_counts": fc[fc["horizon"] == 1]["status"].value_counts().to_dict(),
            **svc.publish_drying(db, issue)}


def run_monthly_update(month: Optional[str] = None, force: bool = False,
                       max_months: int = MAX_CATCH_UP) -> dict:
    """Collecte `month`, ou, sans mois indiqué, tous les mois manquants depuis le dernier mois en base."""
    from ml.forecasting import load_bundle

    bundle = load_bundle()
    if abs(bundle["critical_fill"] - settings.critical_fill) > 1e-9:
        logger.warning("CRITICAL_FILL (%.2f) différent du seuil d'entraînement du modèle (%.2f)",
                       settings.critical_fill, bundle["critical_fill"])

    EarthEngineClient().initialize()
    db = SessionLocal()
    try:
        if month:
            todo, deferred = ([] if svc.month_observed(db, month) and not force else [month]), 0
            if not todo:
                logger.info("Mois %s déjà collecté : collecte ignorée", month)
        else:
            todo, deferred = plan_months(svc.latest_observed_month(db), last_available_month(), max_months)
            if deferred:
                logger.warning("%d mois de retard en plus : reportés au passage suivant", deferred)

        collected, warnings = [], []
        if todo:
            regions, hybas = svc.region_geojson(db), svc.modelable_hybas(db)
        for m in todo:
            logger.info("Collecte v3 %s : %d réservoirs", m, len(regions))
            df = collect_month(m, regions, hybas, bundle)
            n = svc.upsert_observations(db, df)
            db.commit()     # le mois est acquis même si un mois suivant échoue
            collected.append({"month": m, "reservoirs": n, "sources": df["area_source"].value_counts().to_dict()})
            warnings += quality_warnings(df, m)
            logger.info("Mois %s enregistré : %s", m, collected[-1]["sources"])

        # Une émission par mois collecté, dans l'ordre : l'archive des bulletins reste complète
        latest = svc.latest_observed_month(db)
        issues = [c["month"] for c in collected] or [month or latest.strftime("%Y-%m")]
        for issue in issues:
            summary = forecast_and_publish(db, bundle, issue)
            db.commit()

        # Bilan des prévisions qui visaient les mois que l'on vient de mesurer
        verification = svc.verification_by_horizon(db, [c["month"] for c in collected]) if collected else []
        summary.update(collected=sum(c["reservoirs"] for c in collected), months=collected,
                       deferred_months=deferred, warnings=warnings, verification=verification, **freshness(latest))
        for w in warnings:
            logger.warning("Qualité : %s", w)
        logger.info("Mise à jour mensuelle : %s", summary)
        return summary
    except Exception:
        db.rollback()
        logger.exception("Échec de la mise à jour mensuelle")
        raise
    finally:
        db.close()
