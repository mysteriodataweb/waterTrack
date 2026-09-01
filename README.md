# 💧 WaterTracker Afrique — Surveillance des ressources en eau par satellite

> Suivi temps réel de la ressource en eau en Afrique de l'Ouest (Burkina Faso) à partir de **données satellite réelles (Google Earth Engine)**, analysées par **Machine Learning** et **prévision de tarissement**, avec recommandations générées par **IA**.

![Stack](https://img.shields.io/badge/Front-React%20%2B%20TypeScript-61dafb) ![Stack](https://img.shields.io/badge/Back-FastAPI%20%2B%20Python-009688) ![Stack](https://img.shields.io/badge/DB-PostgreSQL%20%2B%20PostGIS-336791) ![Stack](https://img.shields.io/badge/ML-RandomForest%20%2B%20Prophet-ff69b4)

---

## Aperçu

WaterTracker supervise un réseau de **sources / points d'eau** (barrages, retenues, forages) autour de Ouagadougou. Le pipeline ingère des images satellite, estime l'indice d'eau NDWI, entraîne un modèle de tarissement, et expose le tout via une API + une carte interactive.

### Ce que fait le système
- 🛰️ **Collecte satellite** — Google Earth Engine : estimation du NDWI (indice d'eau) par source et par période.
- 🤖 **Machine Learning** — RandomForest (12 features) pour le score de risque de chaque source.
- 📉 **Prévision de tarissement** — Prophet : courbe d'évolution + date estimée de tarissement (CDF).
- 🧠 **Recommandations IA** — générées par LLM (Groq / Qwen) par source.
- 🗺️ **Carte interactive** — navigation, filtres par zone/statut, popups, numérotation par zone.
- 📊 **Rapport historique** — courbe d'évolution NDWI, KPIs, top sources à risque, export CSV.

---

## Architecture (monorepo)

```
backend/     Backend Python / FastAPI
frontend/    Frontend React + TypeScript (Vite, shadcn/ui, Leaflet)
```

### Backend — `backend/`
| Couche | Techno |
|--------|--------|
| API | FastAPI + Pydantic v2 |
| Base de données | PostgreSQL **+ PostGIS** (pg8000) |
| Collecte satellite | Google Earth Engine (`app/collectors/`) |
| ML | scikit-learn RandomForest (`ml/train.py`) |
| Prévision | Prophet (`app/services/prophet_service.py`) |
| Recommandations IA | Groq / Qwen (`app/services/llm.py`) |
| Navigation | OpenRouteService (`app/routes/navigation.py`) |
| Scheduler | APScheduler (`app/collectors/scheduler.py`) |

### Frontend — `frontend/`
- React 19 + TypeScript + Vite
- Carte : Leaflet + OpenStreetMap (fond sombre)
- UI : shadcn/ui (Radix), icônes lucide-react
- Panneaux : Accueil, Analyse, Navigation, Rapports
- Fonds neutres / translucides laissant voir la carte

---

## API — principaux endpoints

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/water-sources` | Sources paginées (avec labels de zone, score de risque, NDWI) |
| `GET` | `/api/water-sources/{id}/prediction` | Prédiction de tarissement + recommandations |
| `GET` | `/api/report/summary` | Rapport historique agrégé (tendance NDWI, zones, top risque) |
| `GET` | `/api/health` | État de santé du service |
| `POST` | `/api/admin/recompute` | Recalcul des scores de risque |

> La config (clés GEE/Groq/ORS, URL DB) se fait via `.env` — voir `backend/.env.example`.

---

## Démarrage local

### 1. Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
cp .env.example .env             # renseigner les clés (DB, GEE, GROQ, ORS)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2. Frontend
```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

> Le frontend appelle le backend via `VITE_API_URL` (défaut `http://127.0.0.1:8000`).

---

## Prérequis
- Python 3.11+ , Node 20+
- Comptes : **Google Earth Engine**, **Groq** (LLM), **OpenRouteService** (navigation)
- Base PostgreSQL + extension PostGIS

---

## Tests
```bash
cd backend
pytest -q          # 15 tests (API, prédiction, prophet)
```

---

## Roadmap
- [ ] Déploiement cloud (backend + DB Postgres managée)
- [ ] Authentification / rôles utilisateur
- [ ] Alertes automatisées (email / mobile) sur seuils de tarissement
- [ ] Extension à d'autres bassins d'Afrique de l'Ouest

---

*Projet de veille hydrique — données satellite réelles, IA explicable.*
