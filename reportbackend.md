# Rapport Backend WaterTracker

## Architecture

Backend **FastAPI** (Python) avec **PostgreSQL/PostGIS** pour la base de données géospatiale. Un seul router (`/api`) avec 7 endpoints.

## Ce qu'il fait concrètement

### 1. Gestion des sources d'eau (`/api/water-sources`)

- Stocke des points géographiques de sources d'eau dans Ouagadougou / Burkina Faso
- Chaque source a : géométrie PostGIS, NDWI moyen (indice d'eau satellite), score de risque, statut (actif / à risque / tarí)

### 2. Prédiction ML (`/api/predict` et `/api/update-all-scores`)

- Modèle **Random Forest** entraîné sur des données historiques NDWI
- Prédit un score de risque (0.0 → actif, 0.5 → à risque, 0.9 → tarí)
- Fallback automatique par règles NDWI si le modèle ML est absent

### 3. Prédiction de tarissement (`/api/water-sources/{id}/prediction`)

- Utilise **Facebook Prophet** (séries temporelles) pour prédire l'évolution du NDWI sur 3 semestres
- Estime la **date de tarissement** future d'une source
- Calcule la vitesse de dégradation (rapide / lente / stable)

### 4. Recommandations IA (`app/services/gemini.py`)

- Mal nommé : utilise en réalité **Groq** (LLaMA 3.3 70B), pas Gemini
- Génère des recommandations en français adaptées à 4 profils : ONG, gouvernement, agent terrain, communauté
- Concrètement : "quand tarí, quoi faire" selon le rôle de l'utilisateur

### 5. Navigation (`/api/navigation/route` et `/api/navigation/reverse`)

- Itinéraires (voiture / pied / vélo) via **OpenRouteService**
- Géocodage inverse (trouver l'adresse d'un point GPS)

## Scripts hors-API (data pipeline)

| Script | Rôle |
|---|---|
| `import_data.py` | Importe un GeoJSON dans PostgreSQL |
| `train_model.py` / `train_model_v2.py` | Entraîne les modèles ML |
| `predict_tarissement.py` | Batch prediction pour toutes les sources |
| `recalculate_risk_scores.py` | Recalcule les scores par règles NDWI |
| `diagnostic.py` | Analyse exploratoire des données |

## Endpoints

| Méthode | Chemin | Description |
|---|---|---|
| GET | `/api/water-sources` | Liste toutes les sources d'eau |
| GET | `/api/water-sources/{id}` | Détail d'une source |
| POST | `/api/predict` | Prédiction ML sur données arbitraires |
| POST | `/api/update-all-scores` | Recalcul batch de tous les scores |
| POST | `/api/navigation/route` | Itinéraire entre 2 points |
| GET | `/api/navigation/reverse` | Géocodage inverse |
| GET | `/api/water-sources/{id}/prediction` | Prédiction Prophet + recommandation IA |

## En résumé

C'est un **système d'alerte précoce de tarissement de sources d'eau** au Burkina Faso, basé sur des données satellite (NDWI). Il prédit quelles sources vont sécher, quand, et génère des recommandations actionnables pour différents acteurs (ONG, gouvernement, communautés).

---

## Limites

### 1. Sécurité

- **Clés API exposées en dur dans le `.env`** : le fichier `.env` contient des clés API (Groq, OpenRouteService) et le mot de passe de la base de données. Ces clés ne doivent jamais être versionnées dans Git.
- **CORS totalement ouvert** (`allow_origins=["*"]`) : n'importe quel site peut appeler l'API, ce qui est un risque en production.
- **Pas d'authentification** : aucun endpoint n'est protégé. N'importe qui peut modifier les scores, lancer des prédictions, etc.
- **Pas de validation des entrées** : le endpoint `/api/predict` accepte un `dict` brut sans aucune validation Pydantic.

### 2. Architecture et code

- **`schemas.py` est vide** : aucune validation Pydantic n'est utilisée pour les réponses ou les requêtes.
- **Nom du fichier `gemini.py` trompeur** : le service utilise Groq, pas Gemini.
- **Pas de `__init__.py` dans `routes/`** : peut poser des problèmes d'import dans certains contextes.
- **Fichiers racine mélangés** : des scripts de training, diagnostics et utilitaires sont à la racine du backend, sans organisation claire.
- **URLs avec chemins absolus Windows** : certains scripts contiennent des chemins comme `D:\\Dossiers\\...`, ce qui casse sur d'autres machines.
- **Pas de gestion d'erreurs propre** : beaucoup de `try/except` avec fallback silencieux, ce qui rend le debugging difficile.

### 3. Modèle ML et données

- **Modèle entraîné sur peu de données** : le dataset historique semble limité (quelques centaines de lignes), ce qui affecte la fiabilité des prédictions.
- **Pas de pipeline d'entraînement automatisé** : les modèles sont entraînés manuellement via des scripts, sans suivi de version ni reproductibilité garantie.
- **Pas de métriques de performance en production** : aucun suivi de la qualité des prédictions une fois déployé.
- **Probabilité de tarissement calculée de manière naïve** : `(1 - (ndwi + 0.5)) * 100` n'est pas une vraie probabilité statistique.
- **Données manquantes comblées par des valeurs par défaut** : latitude/longitude par défaut (12.36, -1.52), NDVI à 0, saison "seche". Ces approximations biaisent les prédictions.

### 4. Performance et scalabilité

- **Pas de cache** : les données historiques CSV sont rechargées à chaque appel Prophet. Pas de Redis ni de cache en mémoire.
- **Requêtes N+1** : `GET /water-sources` fait une requête SQL par source pour récupérer la géométrie (au lieu d'un seul `JOIN`).
- **Pas de pagination** : les endpoints retournent toutes les données d'un coup.
- **Prophet entraîné à chaque requête** : le modèle de série temporelle est réentraîné pour chaque appel de prédiction, ce qui est coûteux.

### 5. Déploiement et maintenance

- **Pas de tests unitaires** : aucun fichier de test pour l'API.
- **Pas de Docker ni de configuration de déploiement**.
- **Pas de documentation API** (au-delà de la doc Swagger automatique).
- **Pas de logging structuré** : uniquement des `print()` dans le code.
- **Pas de health check** : pas d'endpoint `/health` pour vérifier l'état du service.

---

## Recommandations

### Priorité haute

1. **Sécuriser le `.env`** : ajouter `.env` au `.gitignore` et ne jamais commiter de clés API. Utiliser des variables d'environnement en production.
2. **Ajouter l'authentification** : implémenter JWT ou une authentification par clé API pour protéger les endpoints sensibles (`/update-all-scores`, `/predict`).
3. **Restreindre le CORS** : configurer `allow_origins` avec les domaines autorisés uniquement (ex: `["http://localhost:3000"]` en dev).
4. **Valider les entrées** : créer des schémas Pydantic dans `schemas.py` pour toutes les requêtes et réponses API.

### Priorité moyenne

5. **Corriger les chemins absolus** : remplacer tous les `D:\\Dossiers\\...` par des chemins relatifs (`pathlib.Path` ou `os.path`).
6. **Renommer `gemini.py`** en `groq.py` ou `llm.py` pour refléter le vrai service utilisé.
7. **Optimiser les requêtes** : corriger le problème N+1 dans `GET /water-sources` avec un `JOIN` ou `ST_AsGeoJSON` dans la requête principale.
8. **Mettre en cache les données Prophet** : charger l'historique une fois au démarrage ou utiliser un cache LRU, au lieu de relire le CSV à chaque requête.
9. **Ajouter un endpoint `/health`** : retourner l'état de la base de données et des services externes.
10. **Structurer le projet** : séparer les scripts ML dans un dossier `scripts/` ou `ml/`, distinct de l'API.

### Priorité basse

11. **Ajouter des tests** : créer des tests unitaires pour les services (prediction, Prophet, Groq) et des tests d'intégration pour les endpoints.
12. **Dockeriser l'application** : créer un `Dockerfile` et un `docker-compose.yml` pour un déploiement reproductible.
13. **Mettre en place du logging** : remplacer les `print()` par un vrai système de logging Python (`logging` module).
14. **Ajouter de la pagination** : paginer les résultats de `GET /water-sources` pour gérer les gros volumes de données.
15. **Versionner les modèles ML** : utiliser MLflow ou un système similaire pour tracer les versions de modèles, leurs métriques et leurs artefacts.

---

## Évolution : Surveillance en temps réel

### État actuel vs cible

| Aspect | Actuel | Cible |
|---|---|---|
| Source de données | CSV statiques importés manuellement | Images satellites collectées automatiquement (Sentinel-2, Landsat) |
| Fréquence de mise à jour | Semestrielle (manuel) | Hebdomadaire à quotidienne (automatique) |
| Calcul NDWI | Fait à l'avance, stocké en CSV | Calculé en temps réel à l'arrivée de chaque nouvelle image |
| Alertes | Aucune | Notification automatique (email, SMS, push) quand NDWI < seuil critique |
| Prédictions | Ponctuelles (à la demande) | Planifiées automatiquement après chaque mise à jour de données |
| Monitoring | Rien | Dashboard temps réel avec carte animée et état des sources |
| Orchestration | Scripts lancés à la main | Pipeline automatisé avec retry, logs et alertes d'échec |

### Architecture cible

```
┌──────────────────────────────────────────────────────────────────┐
│                     PIPELINE TEMPS RÉEL                          │
│                                                                  │
│  ┌─────────────┐    ┌──────────────────┐    ┌────────────────┐  │
│  │  Sentinel-2  │───▶│  Collecteur      │───▶│  Calcul NDWI   │  │
│  │  Landsat     │    │  (cron/airflow)  │    │  (par source)  │  │
│  └─────────────┘    └──────────────────┘    └───────┬────────┘  │
│                                                      │           │
│                                                      ▼           │
│  ┌─────────────┐    ┌──────────────────┐    ┌────────────────┐  │
│  │  Dashboard   │◀──│  API WebSocket   │◀───│  Mise à jour   │  │
│  │  temps réel  │    │  (FastAPI WS)    │    │  PostgreSQL    │  │
│  └─────────────┘    └──────────────────┘    └───────┬────────┘  │
│                                                      │           │
│                                                      ▼           │
│  ┌─────────────┐    ┌──────────────────┐    ┌────────────────┐  │
│  │  Email/SMS   │◀──│  Moteur d'alerte │◀───│  Comparaison   │  │
│  │  Push notif  │    │  (Celery task)   │    │  seuils        │  │
│  └─────────────┘    └──────────────────┘    └────────────────┘  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  MLflow : versionnage des modèles + métriques en prod      │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### Nouveaux composants détaillés

#### 1. Collecteur de données satellite

**Technologie** : Python + Google Earth Engine API (un fichier `ee_utils.py` existe déjà dans `data/`)

**Rôle** :
- Télécharger automatiquement les images Sentinel-2/Landsat sur la zone du Burkina Faso
- Filtrer par date, couverture nuageuse (< 20%), zone géographique
- Calculer le NDWI pour chaque source d'eau connue
- Stocker les résultats dans PostgreSQL (nouvelle table `ndwi_observations`)

**Fréquence** : Hebdomadaire (Sentinel-2 a une revisite de 5 jours)

**Fichier à créer** : `services/collector.py`

```python
# Pseudo-code
def collect_ndwi_weekly():
    sources = db.query(WaterSource).all()
    for source in sources:
        image = get_latest_sentinel2_image(source.geometry, max_cloud=20)
        ndwi = calculate_ndwi(image, source.geometry)
        save_observation(source.id, ndwi, date=today)
```

#### 2. Table d'observations temps réel

**Nouvelle table PostgreSQL** :

```sql
CREATE TABLE ndwi_observations (
    id            SERIAL PRIMARY KEY,
    source_id     INTEGER REFERENCES water_sources(id),
    ndwi_value    FLOAT NOT NULL,
    observation_date DATE NOT NULL,
    satellite     VARCHAR(50),  -- 'sentinel-2', 'landsat-8'
    cloud_cover   FLOAT,
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ndwi_source_date
ON ndwi_observations(source_id, observation_date DESC);
```

#### 3. Moteur d'alertes

**Technologie** : Celery + Redis (task queue asynchrone)

**Rôle** :
- Après chaque insertion d'observation, comparer le NDWI au seuil critique
- Si NDWI < 0.1 → alerte URGENTE
- Si NDWI < 0.2 et en baisse → alerte PRÉVENTIVE
- Envoyer les notifications selon les préférences de l'utilisateur

**Fichier à créer** : `services/alerts.py`

```python
# Pseudo-code
@celery_app.task
def check_alerts(source_id, ndwi_value, previous_ndwi):
    if ndwi_value < 0.1:
        send_urgent_alert(source_id, "Tarissement imminent détecté")
    elif ndwi_value < 0.2 and ndwi_value < previous_ndwi:
        send_preventive_alert(source_id, "Baisse significative du NDWI")
```

**Canaux de notification** :

| Canal | Technologie | Usage |
|---|---|---|
| Email | SendGrid / SMTP | Rapports périodiques, alertes non urgentes |
| SMS | Twilio / Africa's Talking | Alertes URGENTES (agents terrain) |
| Push | Firebase Cloud Messaging | Application mobile |
| Webhook | HTTP POST | Intégration avec d'autres systèmes |

#### 4. API temps réel (WebSocket)

**Technologie** : FastAPI WebSocket (natif, pas de dépendance supplémentaire)

**Rôle** :
- Pousser les mises à jour en temps réel vers le frontend
- Envoyer les nouvelles observations NDWI dès qu'elles sont calculées
- Notifier les changements de statut d'une source

**Fichier à créer** : `routes/websocket.py`

```python
# Pseudo-code
from fastapi import WebSocket

connected_clients: list[WebSocket] = []

@router.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except:
        connected_clients.remove(websocket)

async def broadcast_update(data: dict):
    for client in connected_clients:
        await client.send_json(data)
```

#### 5. Orchestration des tâches

**Option A (simple)** : APScheduler intégré à FastAPI

```python
# Dans main.py
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(collect_ndwi_weekly, 'cron', day_of_week='mon', hour=6)
scheduler.add_job(retrain_model_monthly, 'cron', day=1, hour=3)
scheduler.start()
```

**Option B (production)** : Apache Airflow

```
dags/
  watertracker_dag.py
    ├── collect_satellite_data     (hebdo, lundi 6h)
    ├── calculate_ndwi             (après collecte)
    ├── check_alerts               (après calcul NDWI)
    ├── retrain_model              (mensuel, 1er du mois 3h)
    └── send_weekly_report         (hebdo, vendredi 8h)
```

#### 6. Dashboard temps réel

**Technologie** : Frontend React/Next.js avec carte Leaflet/Mapbox

**Fonctionnalités** :
- Carte interactive des sources avec code couleur (vert/jaune/rouge)
- Mise à jour automatique via WebSocket (pas de refresh manuel)
- Graphique d'évolution NDWI par source (historique + prédiction)
- Système de notifications dans l'interface
- Filtres par zone, statut, niveau de risque

### Planning d'implémentation

| Phase | Durée | Contenu |
|---|---|---|
| **Phase 1** — Fondations | 2-3 semaines | Table `ndwi_observations`, collecteur Sentinel-2, tâche Celery basique |
| **Phase 2** — Alertes | 1-2 semaines | Moteur d'alertes, envoi email/SMS, préférences utilisateur |
| **Phase 3** — Temps réel | 2 semaines | WebSocket, broadcast des mises à jour, dashboard carte |
| **Phase 4** — ML auto | 1-2 semaines | Réentraînement automatique des modèles, MLflow |
| **Phase 5** — Production | 1-2 semaines | Docker, Airflow, monitoring (Prometheus/Grafana), tests |

**Durée totale estimée** : 7 à 11 semaines

### Dépendances Python supplémentaires

```
# Ajouter à requirements.txt
celery[redis]        # Task queue asynchrone
redis                # Backend Celery
earthengine-api      # Google Earth Engine (collecte satellite)
sendgrid             # Envoi d'emails
twilio               # Envoi de SMS (optionnel)
mlflow               # Versionnage de modèles
apscheduler          # Planification de tâches (option simple)
websockets           # WebSocket (déjà inclus dans FastAPI)
prometheus-client    # Métriques (optionnel)
```

### Fichiers à créer

```
watertracker-backend/
├── services/
│   ├── collector.py          # Collecte satellite + calcul NDWI
│   ├── alerts.py             # Moteur d'alertes
│   ├── groq.py               # Renommé depuis gemini.py
│   └── scheduler.py          # Configuration des tâches planifiées
├── routes/
│   ├── water.py              # Existant
│   └── websocket.py          # Nouveau : endpoints WebSocket
├── ml/
│   ├── train.py              # Depuis train_model.py
│   ├── train_v2.py           # Depuis train_model_v2.py
│   └── evaluate.py           # Nouveau : évaluation en prod
├── scripts/
│   ├── import_data.py        # Depuis racine
│   ├── recalculate_scores.py # Depuis racine
│   └── diagnostic.py         # Depuis racine
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml    # API + Redis + PostgreSQL + Celery worker
└── tests/
    ├── test_api.py
    ├── test_prediction.py
    └── test_alerts.py
```

### Considérations techniques

- **Google Earth Engine** nécessite un compte GEE (gratuit pour usage non commercial) et une authentification par clé de service
- **Sentinel-2** : données免费 via GEE ou Copernicus Open Access Hub
- **Latence** : le calcul NDWI satellite a un délai de 1-3 jours après la prise de l'image (pas vraiment "temps réel" mais quasi-continu)
- **Coût** : SendGrid/Twilio ont des tiers gratuits, GEE est gratuit, Redis peut tourner en local ou sur un VPS minimal
- **Scalabilité** : l'architecture Celery permet d'ajouter des workers si le volume de sources augmente
