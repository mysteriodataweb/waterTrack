from __future__ import annotations

import logging
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import NdwiObservation

logger = logging.getLogger(__name__)

# Seuil NDWI sous lequel une source est considérée "tarie".
DRY_NDWI_THRESHOLD = 0.2


def _periode_to_year_semester(periode: str) -> tuple[int, int] | None:
    """'2024-S1' -> (2024, 1). Retourne None si format inattendu."""
    parts = periode.split("-")
    if len(parts) != 2:
        return None
    try:
        annee = int(parts[0])
        semestre = int(parts[1].replace("S", ""))
    except ValueError:
        return None
    if not (1 <= semestre <= 2):
        return None
    return annee, semestre


def _periode_to_date(periode: str) -> date | None:
    ys = _periode_to_year_semester(periode)
    if ys is None:
        return None
    annee, semestre = ys
    month = 1 if semestre == 1 else 7
    return date(annee, month, 1)


class ProphetUnavailableError(RuntimeError):
    """Le module 'prophet' n'est pas installé."""


def _load_history(db: Session, source_id: int) -> pd.DataFrame:
    rows = db.execute(
        select(NdwiObservation).where(
            NdwiObservation.source_id == source_id,
            NdwiObservation.ndwi.isnot(None),
        ).order_by(NdwiObservation.periode)
    ).scalars().all()

    records = []
    for row in rows:
        records.append({
            "periode": row.periode,
            "ndwi": row.ndwi,
            "date": _periode_to_date(row.periode),
        })

    df = pd.DataFrame(records)
    if df.empty:
        return df
    df = df.dropna(subset=["periode", "ndwi"]).sort_values("periode")
    return df


def _predict_fallback(db: Session, source_id: int, df: pd.DataFrame) -> dict:
    """Prédiction statistique sans Prophet (régression linéaire sur la pente NDWI).

    Permet à l'API de rester fonctionnelle même quand 'prophet' (dépendance
    optionnelle, lourde) n'est pas installé — utile sur le plan free de Render.
    """
    import numpy as _np

    ndwi_values = df["ndwi"].values.astype(float)
    n = len(ndwi_values)
    x = _np.arange(n, dtype=float)
    slope, intercept = _np.polyfit(x, ndwi_values, 1)

    last_periode = str(df["periode"].iloc[-1])
    ys = _periode_to_year_semester(last_periode)
    last_year, last_sem = ys if ys else (2024, 2)

    predictions = []
    date_tarissement = None
    total_proba_first_tarissement = 0.0
    survived = 1.0

    for i in range(1, 4):
        if last_sem == 1:
            y, s = last_year, 2
        else:
            y, s = last_year + 1, 1
        label = f"{y}-S{s}"
        last_year, last_sem = y, s

        # Prolongement linéaire de la tendance historique.
        future_x = float(n - 1 + i)
        ndwi_predit = max(0.0, float(intercept + slope * future_x))

        # Écart-type estimé à partir de l'erreur résiduelle du fit.
        resid = ndwi_values - (intercept + slope * x)
        sd = max(float(_np.std(resid)), 1e-6)

        from scipy import stats
        proba_periode = float(stats.norm.cdf((DRY_NDWI_THRESHOLD - ndwi_predit) / sd))
        proba_periode = max(0.0, min(1.0, proba_periode))
        proba_first = survived * proba_periode
        total_proba_first_tarissement += proba_first
        survived *= 1.0 - proba_periode

        predictions.append({
            "periode": label,
            "ndwi_predit": round(ndwi_predit, 4),
            "ndwi_min": round(max(0.0, ndwi_predit - 1.28 * sd), 4),
            "ndwi_max": round(ndwi_predit + 1.28 * sd, 4),
            "probabilite_tarissement": round(proba_first * 100, 1),
        })

        if date_tarissement is None and ndwi_predit < DRY_NDWI_THRESHOLD:
            date_tarissement = label

    tendance = float(slope)
    if tendance < -0.05:
        vitesse = "rapide"
    elif tendance < 0:
        vitesse = "lente"
    else:
        vitesse = "stable"

    confiance = min(int(n / 10 * 100), 100)

    return {
        "water_source": source_id,
        "ndwi_actuel": round(float(ndwi_values[-1]), 4),
        "tendance": round(tendance, 4),
        "vitesse_degradation": vitesse,
        "date_tarissement": date_tarissement,
        "confiance": confiance,
        "probabilite_tarissement": round(total_proba_first_tarissement * 100, 1),
        "predictions": predictions,
        "modele": "regression_linéaire (fallback, sans prophet)",
    }


def predire_tarissement(db: Session, source_id: int) -> dict:
    df = _load_history(db, source_id)
    if len(df) < 3:
        return {"erreur": "Pas assez de données historiques (minimum 3 périodes)"}

    # ---------- Prophet (optionnel) ----------
    try:
        from prophet import Prophet  # import retardé : dépendance lourde & optionnelle
    except ModuleNotFoundError:  # pragma: no cover
        logger.info("prophet absent → prédiction statistique de secours (source %d)", source_id)
        return _predict_fallback(db, source_id, df)

    hist = df[["periode", "ndwi"]].copy()
    hist["ds"] = hist["periode"].apply(_periode_to_date)
    hist["y"] = hist["ndwi"]
    hist = hist[["ds", "y"]].dropna().sort_values("ds")

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        interval_width=0.80,
    )
    model.fit(hist)

    # Horizon : 3 prochaines périodes semestrielles après la dernière connue.
    last = hist["ds"].iloc[-1]
    last_year = last.year
    last_sem = 2 if last.month >= 7 else 1
    future = []
    for i in range(1, 4):
        ys = (last_year, last_sem)
        # prochaine période
        y, s = ys
        if s == 1:
            y, s = y, 2
        else:
            y, s = y + 1, 1
        label = f"{y}-S{s}"
        future.append({"ds": date(y, 1 if s == 1 else 7, 1), "periode": label})
        last_sem = s
        last_year = y

    future_df = pd.DataFrame(future)
    forecast = model.predict(future_df)

    # ---------- Tendance ----------
    ndwi_values = hist["y"].values
    tendance = float(np.mean(np.diff(ndwi_values[-4:]))) if len(ndwi_values) >= 4 else 0.0

    if tendance < -0.05:
        vitesse = "rapide"
    elif tendance < 0:
        vitesse = "lente"
    else:
        vitesse = "stable"

    # ---------- Prédictions avec VRAIE probabilité ----------
    predictions = []
    date_tarissement = None
    total_proba_first_tarissement = 0.0
    survived = 1.0  # probabilité d'avoir survécu jusqu'ici (sans tarir avant)

    for i, row in forecast.iterrows():
        ndwi_predit = float(row["yhat"])
        ndwi_min = float(row["yhat_lower"])
        ndwi_max = float(row["yhat_upper"])
        label = str(future_df["periode"].iloc[i])

        # Probabilité que NDWI < seuil SUR CETTE période, en supposant une
        # distribution normale centrée sur yhat avec écart-type issu de yhat_lower.
        sd = max((ndwi_predit - ndwi_min) / 1.28, 1e-6)  # 80% intervalle (z=1.28)
        from scipy import stats
        proba_periode = float(stats.norm.cdf((DRY_NDWI_THRESHOLD - ndwi_predit) / sd))
        proba_periode = max(0.0, min(1.0, proba_periode))

        # Probabilité cumulative = première période où la source tarit.
        proba_first = survived * proba_periode
        total_proba_first_tarissement += proba_first
        survived *= 1.0 - proba_periode

        predictions.append({
            "periode": label,
            "ndwi_predit": round(ndwi_predit, 4),
            "ndwi_min": round(ndwi_min, 4),
            "ndwi_max": round(ndwi_max, 4),
            "probabilite_tarissement": round(proba_first * 100, 1),
        })

        if date_tarissement is None and ndwi_predit < DRY_NDWI_THRESHOLD:
            date_tarissement = label

    # Confiance basée sur le nombre de périodes (plafonné à 100).
    confiance = min(int(len(df) / 10 * 100), 100)

    return {
        "water_source": source_id,
        "ndwi_actuel": round(float(ndwi_values[-1]), 4),
        "tendance": round(tendance, 4),
        "vitesse_degradation": vitesse,
        "date_tarissement": date_tarissement,
        "confiance": confiance,
        "probabilite_tarissement": round(total_proba_first_tarissement * 100, 1),
        "predictions": predictions,
        "modele": "prophet",
    }
