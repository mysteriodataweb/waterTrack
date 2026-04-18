import pandas as pd
import numpy as np
import joblib
from app.database import SessionLocal
from app.models import WaterSource
import json

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        return super().default(obj)

# Charger le modèle et les encodeurs
model     = joblib.load('app/models/watertracker_rf.pkl')
scaler    = joblib.load('app/models/scaler.pkl')
le_saison = joblib.load('app/models/encoder_saison.pkl')
seuils    = joblib.load('app/models/seuils.pkl')

# Charger l'historique des sources
df =pd.read_csv('D:\\Dossiers\\WaterTracker_Project\\watertracker-backend\\data\\historique\\ndwi_sources_historique.csv')
df = df.dropna(subset=['ndwi_moyen'])
df = df.dropna(subset=['ndwi_moyen'])
df = df.sort_values(['source_id', 'periode'])

# Périodes futures à prédire
periodes_futures = [
    {'label': '2025-S1', 'saison': 'seche',  'annee': 2025, 'semestre': 1, 'jours': 90},
    {'label': '2025-S2', 'saison': 'pluies', 'annee': 2025, 'semestre': 2, 'jours': 180},
    {'label': '2026-S1', 'saison': 'seche',  'annee': 2026, 'semestre': 1, 'jours': 270},
]

SEUIL_TARISSEMENT = 0.0  # NDWI en dessous duquel = tari

def get_recommandation(risk_score, jours):
    if risk_score >= 0.7:
        urgence = "URGENT" if jours <= 90 else "CRITIQUE"
        return {
            "niveau":       urgence,
            "ONG":          f"Intervention requise — approvisionnement alternatif dans {jours} jours",
            "gouvernement": f"Déclencher plan d'urgence eau — tarissement prévu dans {jours} jours",
            "communaute":   "Rationner l'eau immédiatement, identifier source alternative"
        }
    elif risk_score >= 0.4:
        return {
            "niveau":       "SURVEILLANCE",
            "ONG":          "Surveiller cette source — risque modéré détecté",
            "gouvernement": "Planifier intervention préventive",
            "communaute":   "Économiser l'eau, signaler toute baisse visible"
        }
    else:
        return {
            "niveau":       "STABLE",
            "ONG":          "Source stable — surveillance mensuelle suffisante",
            "gouvernement": "Aucune action immédiate requise",
            "communaute":   "Source fiable pour les prochains mois"
        }

def predire_source(source_id, historique):
    """Prédit le risque de tarissement pour une source donnée"""

    # Historique trié de cette source
    hist = historique[historique['source_id'] == source_id].sort_values('periode')

    if len(hist) < 3:
        return None

    # Valeurs historiques
    ndwi_values = hist['ndwi_moyen'].values
    ndvi_values = hist['ndvi_moyen'].fillna(0).values

    # Tendances
    tendance      = np.mean(np.diff(ndwi_values[-4:])) if len(ndwi_values) >= 4 else np.mean(np.diff(ndwi_values))
    ndwi_moy_src  = np.mean(ndwi_values)
    latitude      = hist['latitude'].iloc[0]
    longitude     = hist['longitude'].iloc[0]

    predictions = []
    ndwi_courant = ndwi_values[-1]

    for p in periodes_futures:
        # Encoder la saison
        try:
            saison_encoded = le_saison.transform([p['saison']])[0]
        except:
            saison_encoded = 0

        # Features pour le modèle
        ndwi_t1 = ndwi_values[-1] if len(ndwi_values) >= 1 else ndwi_courant
        ndwi_t2 = ndwi_values[-2] if len(ndwi_values) >= 2 else ndwi_courant
        ndwi_t3 = ndwi_values[-3] if len(ndwi_values) >= 3 else ndwi_courant

        features = np.array([[
            ndwi_t1,
            ndwi_t2,
            ndwi_t3,
            tendance,
            ndwi_values[-1] - ndwi_values[-3] if len(ndwi_values) >= 3 else 0,
            ndwi_moy_src,
            np.mean(ndvi_values),
            latitude if pd.notna(latitude) else 12.36,
            longitude if pd.notna(longitude) else -1.52,
            saison_encoded,
            p['annee'],
            p['semestre']
        ]])

        # Prédiction du risk score
        risk_score = float(model.predict(features)[0])
        risk_score = max(0.0, min(1.0, risk_score))

        # NDWI prédit par extrapolation linéaire
        ndwi_predit = ndwi_courant + (tendance * p['semestre'])

        # Probabilité de tarissement
        proba_tarissement = risk_score * 100

        # Recommandation
        recommandation = get_recommandation(risk_score, p['jours'])

        predictions.append({
            'periode':             p['label'],
            'jours':               p['jours'],
            'ndwi_predit':         round(ndwi_predit, 4),
            'risk_score':          round(risk_score, 3),
            'proba_tarissement':   round(proba_tarissement, 1),
            'statut_predit':       recommandation['niveau'],
            'recommandation':      recommandation
        })

        # Mettre à jour ndwi_courant pour la prochaine itération
        ndwi_courant = ndwi_predit

    # Estimer la date de tarissement
    date_tarissement = None
    for pred in predictions:
        if pred['ndwi_predit'] <= SEUIL_TARISSEMENT or pred['risk_score'] >= 0.8:
            date_tarissement = pred['periode']
            break

    return {
        'source_id':         source_id,
        'ndwi_actuel':       round(float(ndwi_values[-1]), 4),
        'tendance':          round(float(tendance), 4),
        'date_tarissement':  date_tarissement,
        'predictions':       predictions,
        'confiance':         round(min(len(hist) / 10 * 100, 100), 1)
    }

# Appliquer sur toutes les sources
sources_ids = df['source_id'].unique()
print(f"Prédiction pour {len(sources_ids)} sources...")

resultats = []
for sid in sources_ids:
    pred = predire_source(sid, df)
    if pred:
        resultats.append(pred)

# Sauvegarder les résultats
import json
with open('data/predictions.json', 'w') as f:
    json.dump(resultats, f, indent=2, cls=NumpyEncoder)

print(f"\n=== Résultats ===")
print(f"Sources analysées : {len(resultats)}")

# Résumé
vont_tarir_90j  = sum(1 for r in resultats if r['date_tarissement'] == '2025-S1')
vont_tarir_180j = sum(1 for r in resultats if r['date_tarissement'] == '2025-S2')
stables         = sum(1 for r in resultats if r['date_tarissement'] is None)

print(f"Vont tarir dans 90j  : {vont_tarir_90j}")
print(f"Vont tarir dans 180j : {vont_tarir_180j}")
print(f"Stables              : {stables}")

# Afficher exemple
print(f"\n=== Exemple source #0 ===")
print(json.dumps(resultats[0], indent=2, cls=NumpyEncoder))