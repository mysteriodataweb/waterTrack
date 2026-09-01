# WaterTracker Backend v2

Système d'alerte précoce de tarissement des sources d'eau au Burkina Faso
(Ouagadougou). Refonte du backend d'origine basée sur le rapport
`reportbackend.md` : sécurité, fiabilité ML, collecte de données et architecture.

> **Différence clé avec la v1** : ce backend ne copie aucun CSV figé ni mock.
> Il **collecte ses propres données réelles** depuis Google Earth Engine
> (Sentinel-2), calcule le NDWI/NDVI de chaque source, et entraîne le modèle
> sur ces données fraîches. C'est un départ de zéro complet.

---

## Architecture

```
watertracker-backend-v2/
├── app/
│   ├── main.py                 # FastAPI + CORS restreint + health + scheduler
│   ├── config.py               # Lecture .env sécurisée (pydantic-settings)
│   ├── database.py             # SQLAlchemy + PostgreSQL/PostGIS
│   ├── models.py               # WaterSource, NdwiObservation
│   ├── schemas.py              # Validations Pydantic (requêtes + réponses)
│   ├── deps.py                 # Auth par API key (endpoints d'écriture)
│   ├── router.py               # Agrégation des routes
│   ├── routes/                 # water, prediction, navigation, health
│   ├── services/               # ml, prophet, recommande (Groq + fallback)
│   └── collectors/             # earth_engine, ingest, scheduler
├── ml/                         # train.py, evaluate.py + runs/<artifacts>
├── scripts/                    # backfill_ndwi.py
├── tests/                      # tests unitaires
├── .env.example                # modèle de config (sans secrets)
├── requirements.txt
└── README.md
```

## Principes de la refonte

| Problème v1 | Correction v2 |
|---|---|
| Clés API dans le code / `.env` commité | `.env` gitignoré + `config.py` + `.env.example` |
| CORS `*` | `CORS_ORIGINS` configurable (défaut: localhost) |
| Aucune auth | API key requise sur les endpoints d'écriture (`/predict`, `/admin/*`) |
| `schemas.py` vide | Schémas Pydantic partout (requêtes + réponses) |
| `gemini.py` mal nommé (Groq) | `services/llm.py` + `services/recommande.py` (fallback règles) |
| Modèle v1 (score) branché, v2 jamais utilisé | Modèle **v2** branché : "périodes avant tarissement" |
| Features en dur (ndvi=0, lat=12.36...) | Données réelles depuis la base (coord, saison) |
| Probabilité naive `(1-(ndwi+0.5))*100` | **Vraie probabilité** issue du forecast Prophet (CDF normale) |
| N+1 sur /water-sources | Requête unique + pagination |
| Données figées en 2024, collecte manuelle | Collector satellite + scheduler APScheduler (collecte hebdo) |
| Pas de tests / logging / health | Tests pytest, `logging`, endpoint `/health` |

## Démarrage rapide

```bash
# 1. Créer l'environnement
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 2. Configurer les secrets
copy .env.example .env   # puis remplir DATABASE_URL, GROQ_API_KEY, OPENROUTE_API_KEY, GEE_PROJECT

# 3. (Optionnel) Activer l'extension PostGIS + créer les tables au premier lancement

# 4. Lancer la collecte initiale (vraies données satellite, depuis 2020)
python -m scripts.backfill_ndwi --dry-run   # prévisualiser
python -m scripts.backfill_ndwi             # écrire en base

# 5. Entraîner le modèle sur ces données réelles
python -m ml.train
python -m ml.evaluate

# 6. Démarrer l'API
uvicorn app.main:app --reload
```

L'API expose la doc interactive sur `http://localhost:8000/docs`.

## Endpoints

| Méthode | Chemin | Description | Auth |
|---|---|---|---|
| GET | `/api/health` | État DB + services externes | non |
| GET | `/api/water-sources?page=&zone=&status=` | Liste paginée | non |
| GET | `/api/water-sources/{id}` | Détail d'une source | non |
| POST | `/api/predict` | Prédiction risque ML | API key |
| GET | `/api/water-sources/{id}/prediction` | Tarissement Prophet + reco | non |
| POST | `/api/admin/recompute` | Recalcul des scores | API key |
| POST | `/api/admin/collect` | Déclenche collecte satellite | API key |
| POST | `/api/navigation/route` | Itinéraire OpenRouteService | non |
| GET | `/api/navigation/reverse` | Géocodage inverse | non |

## Collecte de données

- **Initiale** : `scripts/backfill_ndwi.py` redétecte les zones d'eau (Sentinel-2),
  calcule NDWI/NDVI par période depuis 2020, et remplit `water_sources` +
  `ndwi_observations`.
- **Continue** : `scheduler.py` (APScheduler) re-collecte la période courante
  toutes les `COLLECT_HOURS` heures. Déclenchable à la main via
  `POST /api/admin/collect`.

> Le climat/altitude/humidité (ERA5) peut être enrichi par observation
> (`NdwiObservation` a déjà les colonnes). Le script de collecte les remplit
> quand la source de données est configurée.

## Sécurité

- `.env` jamais commité (vérifié par `.gitignore`).
- Ne pas committer les `.pkl` de `ml/runs/` ni les données `data/`.
- Définir une `API_KEY` forte pour la production.
