import numpy as np
import joblib
import os
from typing import Optional

class NDWIPredictionService:
    """Règles métier — fallback si modèle ML absent"""

    def get_risk_score(self, ndwi: Optional[float]) -> dict:
        if ndwi is None:
            return {"score": 0.5, "status": "inconnu"}
        if ndwi > 0.4:
            return {"score": 0.1, "status": "actif"}
        elif ndwi > 0.2:
            return {"score": 0.5, "status": "à risque"}
        else:
            return {"score": 0.9, "status": "tari"}


class MLPredictionService:
    """Modèle Random Forest entraîné"""

    def __init__(self):
        self.model    = joblib.load('app/models/watertracker_rf.pkl')
        self.scaler   = joblib.load('app/models/scaler.pkl')
        self.seuils   = joblib.load('app/models/seuils.pkl')
        self.le_saison = joblib.load('app/models/encoder_saison.pkl')

    def get_risk_score(self, data: dict) -> dict:
        try:
            # Encoder la saison
            saison = data.get('saison', 'seche')
            try:
                saison_encoded = self.le_saison.transform([saison])[0]
            except:
                saison_encoded = 0

            features = np.array([[
                data.get('ndwi_t1',        data.get('ndwi_moyen', 0)),
                data.get('ndwi_t2',        data.get('ndwi_moyen', 0)),
                data.get('ndwi_t3',        data.get('ndwi_moyen', 0)),
                data.get('tendance',       0),
                data.get('tendance_long',  0),
                data.get('ndwi_moy_src',   data.get('ndwi_moyen', 0)),
                data.get('ndvi_moyen',     0),
                data.get('latitude',       12.36),
                data.get('longitude',      -1.52),
                saison_encoded,
                data.get('annee',          2024),
                data.get('semestre',       1),
            ]])

            score  = float(self.model.predict(features)[0])
            score  = max(0.0, min(1.0, score))
            status = self._get_status(score)

            return {"score": round(score, 3), "status": status}

        except Exception as e:
            print(f"Erreur ML: {e} → fallback NDWI")
            return NDWIPredictionService().get_risk_score(data.get('ndwi_moyen'))

    def _get_status(self, score: float) -> str:
        if score < 0.3:
            return "actif"
        elif score < 0.6:
            return "à risque"
        else:
            return "tari"


# Charger ML si disponible, sinon fallback NDWI
def get_prediction_service():
    try:
        return MLPredictionService()
    except Exception as e:
        print(f"Modèle ML non disponible ({e}) → règles NDWI")
        return NDWIPredictionService()

PredictionService = get_prediction_service()