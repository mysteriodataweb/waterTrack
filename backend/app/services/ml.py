from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import joblib
import numpy as np

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "ml" / "runs"
DEFAULT_RUN = MODELS_DIR / "latest"


def _resolve_model_dir() -> Optional[Path]:
    """Répertoire du modèle v2 le plus récent (ml/runs/latest ou artifacts par run)."""
    if DEFAULT_RUN.exists() and (DEFAULT_RUN / "model.pkl").exists():
        return DEFAULT_RUN
    # Fallback: premier run trié par date
    if MODELS_DIR.exists():
        runs = sorted(MODELS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        for run in runs:
            if (run / "model.pkl").exists():
                return run
    return None


class MLUnavailableError(RuntimeError):
    """Modèle ML chargé mais non exploitable."""


class PeriodsUntilDryService:
    """Prédiction basée sur le modèle v2 : nombre de périodes avant tarissement (NDWI < 0.2)."""

    def __init__(self, model_dir: Optional[Path] = None):
        self.model = None
        self.scaler = None
        self.le_saison = None
        self.le_ville = None
        self.features = None
        self.metadata = {}
        self.load(model_dir)

    # ------------------------------------------------------------------ #
    def load(self, model_dir: Optional[Path] = None) -> None:
        model_dir = model_dir or _resolve_model_dir()
        if model_dir is None:
            raise MLUnavailableError(
                "Aucun modèle entraîné trouvé dans ml/runs. Lancer `python -m ml.train`."
            )

        try:
            self.model = joblib.load(model_dir / "model.pkl")
            self.scaler = joblib.load(model_dir / "scaler.pkl")
            self.le_saison = joblib.load(model_dir / "encoder_saison.pkl")
            self.le_ville = joblib.load(model_dir / "encoder_ville.pkl")
            feat_file = model_dir / "features.json"
            if feat_file.exists():
                import json
                with open(feat_file, "r", encoding="utf-8") as f:
                    self.features = json.load(f)
            meta_file = model_dir / "metadata.json"
            if meta_file.exists():
                import json as _json
                with open(meta_file, "r", encoding="utf-8") as f:
                    self.metadata = _json.load(f)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Échec du chargement du modèle ML")
            raise MLUnavailableError(f"Modèle ML indisponible : {exc}") from exc

        logger.info("Modèle ML v2 chargé depuis %s", model_dir)

    # ------------------------------------------------------------------ #
    def _to_vector(self, data: dict) -> np.ndarray:
        """Construit le vecteur de features dans l'ORDRE exact du modèle (12 features).

        L'ordre doit correspondre à FEATURES dans ml/train.py :
        ndwi, ndwi_t1, ndwi_t2, ndwi_t3, pente_court, pente_moyen, ndwi_moy_src,
        ndvi, saison_encoded, ville_encoded, latitude, longitude
        """
        ndwi = data.get("ndwi_moyen") or 0.0
        ndwi_t1 = data.get("ndwi_t1") or ndwi
        ndwi_t2 = data.get("ndwi_t2") or ndwi
        ndwi_t3 = data.get("ndwi_t3") or ndwi
        return np.array(
            [
                [
                    ndwi,                                      # ndwi
                    ndwi_t1,                                   # ndwi_t1
                    ndwi_t2,                                   # ndwi_t2
                    ndwi_t3,                                   # ndwi_t3
                    ndwi - ndwi_t1,                            # pente_court
                    ndwi - ndwi_t3,                            # pente_moyen
                    data.get("ndwi_moy_src") or ndwi,          # ndwi_moy_src
                    data.get("ndvi_moyen") or 0.0,             # ndvi
                    data.get("saison_encoded") or 0.0,         # saison_encoded
                    data.get("ville_encoded") or 0.0,          # ville_encoded
                    data.get("latitude") or 12.36,             # latitude
                    data.get("longitude") or -1.52,            # longitude
                ]
            ],
            dtype=float,
        )

    # ------------------------------------------------------------------ #
    def predict_periods_until_dry(self, data: dict) -> Optional[int]:
        """Retourne le nombre de périodes avant tarissement, ou None."""
        if self.model is None:
            return None
        vector = self._to_vector(data)
        if self.scaler is not None:
            vector = self.scaler.transform(vector)
        pred = float(self.model.predict(vector)[0])
        return int(max(1, min(20, round(pred))))

    # ------------------------------------------------------------------ #
    def get_risk_score(self, data: dict) -> dict:
        """Score de risque 0-1 dérivé de la prédiction v2 (périodes avant tarissement)."""
        if self.model is None:
            raise MLUnavailableError("Modèle ML non chargé")
        periods = self.predict_periods_until_dry(data) or 1
        # Mapper : peu de périodes = risque élevé
        score = max(0.0, min(1.0, 1.0 - (periods - 1) / 10.0))
        if score >= 0.6:
            status = "tari"
        elif score >= 0.3:
            status = "à risque"
        else:
            status = "actif"
        return {"score": round(score, 3), "status": status, "periods_until_dry": periods}


# Fallback par règles NDWI — utilisé SEULEMENT si le modèle est absent (et clairement loggé).
class RuleBasedRiskService:
    def get_risk_score(self, data: dict) -> dict:
        ndwi = data.get("ndwi_moyen")
        if ndwi is None:
            return {"score": 0.5, "status": "inconnu", "periods_until_dry": None}
        if ndwi > 0.4:
            return {"score": 0.1, "status": "actif", "periods_until_dry": None}
        if ndwi > 0.2:
            return {"score": 0.5, "status": "à risque", "periods_until_dry": None}
        return {"score": 0.9, "status": "tari", "periods_until_dry": None}


def get_prediction_service() -> PeriodsUntilDryService | RuleBasedRiskService:
    try:
        return PeriodsUntilDryService()
    except MLUnavailableError as exc:
        logger.warning("Modèle ML non disponible (%s) → fallback par règles NDWI", exc)
        return RuleBasedRiskService()


PredictionService = get_prediction_service()
