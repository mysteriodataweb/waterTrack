from __future__ import annotations

import json
import logging
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
    # Fallback: run v2 le plus récent (les runs v3 `forecast_*` ont un autre format)
    if MODELS_DIR.exists():
        runs = sorted(
            (p for p in MODELS_DIR.iterdir() if p.is_dir() and p.name.startswith("run_")),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
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
                with open(feat_file, "r", encoding="utf-8") as f:
                    self.features = json.load(f)
            meta_file = model_dir / "metadata.json"
            if meta_file.exists():
                with open(meta_file, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Échec du chargement du modèle ML")
            raise MLUnavailableError(f"Modèle ML indisponible : {exc}") from exc

        logger.info("Modèle ML v2 chargé depuis %s", model_dir)

    # ------------------------------------------------------------------ #
    def _encode_saison(self, data: dict) -> float:
        """Encode la saison avec l'encodeur de l'entraînement (et non une valeur figée à 0)."""
        if data.get("saison_encoded") is not None:
            return float(data["saison_encoded"])
        saison = data.get("saison")
        if self.le_saison is not None and saison in set(self.le_saison.classes_):
            return float(self.le_saison.transform([saison])[0])
        return 0.0

    def _to_vector(self, data: dict) -> np.ndarray:
        """Construit le vecteur de features dans l'ORDRE exact du modèle (12 features).

        L'ordre doit correspondre à FEATURES dans ml/train.py :
        ndwi, ndwi_t1, ndwi_t2, ndwi_t3, pente_court, pente_moyen, ndwi_moy_src,
        ndvi, saison_encoded, ville_encoded, latitude, longitude

        `_get` teste `is None` : un NDWI de 0.0 est une mesure valide, pas une
        valeur manquante (l'ancien `or` le remplaçait silencieusement).
        """
        def _get(key: str, default: float) -> float:
            value = data.get(key)
            return float(default if value is None else value)

        ndwi = _get("ndwi_moyen", 0.0)
        ndwi_t1 = _get("ndwi_t1", ndwi)
        ndwi_t2 = _get("ndwi_t2", ndwi)
        ndwi_t3 = _get("ndwi_t3", ndwi)
        return np.array(
            [
                [
                    ndwi,                                      # ndwi
                    ndwi_t1,                                   # ndwi_t1
                    ndwi_t2,                                   # ndwi_t2
                    ndwi_t3,                                   # ndwi_t3
                    ndwi - ndwi_t1,                            # pente_court
                    ndwi - ndwi_t3,                            # pente_moyen
                    _get("ndwi_moy_src", ndwi),                # ndwi_moy_src
                    _get("ndvi_moyen", 0.0),                   # ndvi
                    self._encode_saison(data),                 # saison_encoded
                    _get("ville_encoded", 0.0),                # ville_encoded
                    _get("latitude", 12.36),                   # latitude
                    _get("longitude", -1.52),                  # longitude
                ]
            ],
            dtype=float,
        )

    @property
    def _expects_scaled_input(self) -> bool:
        """ml/train.py n'entraîne sur données normalisées que le GradientBoosting.

        La forêt aléatoire est entraînée sur les données brutes : lui appliquer
        le scaler à l'inférence fausse toutes ses prédictions.
        """
        return self.scaler is not None and self.metadata.get("model") == "GradientBoosting"

    # ------------------------------------------------------------------ #
    def predict_periods_until_dry(self, data: dict) -> Optional[int]:
        """Retourne le nombre de périodes avant tarissement, ou None."""
        if self.model is None:
            return None
        vector = self._to_vector(data)
        if self._expects_scaled_input:
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
