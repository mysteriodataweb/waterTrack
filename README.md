# 💧 WaterTracker Africa — Satellite monitoring of water resources

> Monitoring of small reservoirs in West Africa (Burkina Faso) from **real satellite data (Google Earth Engine)**: monthly water surface at **10 m**, **machine-learning forecasts** of reservoir filling 1-3 months ahead, and **AI-generated recommendations**.

![Stack](https://img.shields.io/badge/Front-React%20%2B%20TypeScript-61dafb) ![Stack](https://img.shields.io/badge/Back-FastAPI%20%2B%20Python-009688) ![Stack](https://img.shields.io/badge/DB-PostgreSQL%20%2B%20PostGIS-336791) ![Stack](https://img.shields.io/badge/ML-RandomForest%20%2B%20Prophet-ff69b4)

---

## Overview

WaterTracker monitors a network of **water points** (dams, reservoirs, ponds) around Ouagadougou. The pipeline ingests satellite imagery, measures the water surface of each reservoir every month, forecasts its filling, and exposes everything through an API and an interactive map.

### What the system does
- 🛰️ **Satellite collection** — Google Earth Engine: monthly water surface of each reservoir at 10 m (Sentinel-2 + Sentinel-1), updated automatically.
- 🤖 **Machine learning** — forecast of the reservoir filling ratio 1-3 months ahead (RandomForest), with a prediction interval and the probability of reaching a critical level; monthly bulletin.
- 📉 **Drying-up forecast (v2)** — Prophet: trend curve and estimated drying date.
- 🧠 **AI recommendations** — generated per water point by an LLM (Groq / Qwen).
- 🗺️ **Interactive map** — navigation, filters by zone/status, popups, numbering by zone.
- 📊 **Historical report** — NDWI trend, KPIs, top at-risk sources, CSV export.

---

## Architecture (monorepo)

```
backend/     Python / FastAPI backend
frontend/    React + TypeScript frontend (Vite, shadcn/ui, Leaflet)
```

### Backend — `backend/`
| Layer | Technology |
|--------|--------|
| API | FastAPI + Pydantic v2 |
| Database | PostgreSQL **+ PostGIS** (pg8000) |
| Satellite collection | Google Earth Engine (`app/collectors/`) |
| Forecasting model (v3) | scikit-learn (`ml/features.py`, `ml/forecasting.py`) |
| Drying-up forecast (v2) | Prophet (`app/services/prophet_service.py`) |
| AI recommendations | Groq / Qwen (`app/services/llm.py`) |
| Navigation | OpenRouteService (`app/routes/navigation.py`) |
| Scheduler | APScheduler (`app/collectors/scheduler.py`) |

### Research notebook — `backend/notebooks/`
`WaterTracker_pipeline.ipynb`: complete, reproducible pipeline from Google Earth Engine extraction
(Sentinel-2 at 10 m + Sentinel-1, CHIRPS, ERA5-Land) to the filling-ratio forecasting model
(temporal validation, calibrated intervals, model card). See `backend/README.md`.

### Frontend — `frontend/`
- React 19 + TypeScript + Vite + Tailwind CSS 4
- Map: Leaflet + OpenStreetMap (light basemap, readable outdoors)
- Pages: home, map (list, reservoir sheet, route, advice), monthly bulletin (table, CSV, print)
- Built around the v3 monthly bulletin: measured fill, 1-3 month forecast, risk of critical level
- See `frontend/README.md`

---

## API — main endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/water-sources` | Paginated water points (zone labels, risk score, NDWI) |
| `GET` | `/api/water-sources/{id}/prediction` | Drying-up forecast + recommendations (v2) |
| `GET` | `/api/water-sources/{id}/forecast` | v3 filling-ratio forecast 1-3 months ahead (interval, probability of critical level) |
| `GET` | `/api/bulletin` | v3 monthly bulletin: all reservoirs ranked by risk (JSON or CSV) |
| `GET` | `/api/reservoirs`, `/api/reservoirs/{id}/history` | v3 reservoirs and their monthly water-surface series (10 m) |
| `GET` | `/api/report/summary` | Aggregated historical report (NDWI trend, zones, top risk) |
| `GET` | `/api/health` | Service health |
| `POST` | `/api/admin/recompute` | Recompute risk scores (API key) |

> Configuration (GEE/Groq/ORS keys, database URL) goes in `.env` — see `backend/.env.example`.

---

## Local setup

### 1. Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
cp .env.example .env             # fill in the keys (DB, GEE, GROQ, ORS)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2. Frontend
```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

> In development the frontend calls `/api` and Vite proxies it to `http://127.0.0.1:8000`. In production, set `VITE_API_URL` at build time.

---

## Requirements
- Python 3.11+, Node 20+
- Accounts: **Google Earth Engine**, **Groq** (LLM), **OpenRouteService** (navigation)
- PostgreSQL database with the PostGIS extension

---

## Tests
```bash
cd backend
pytest -q          # API, predictions, fixes, feature leakage checks, v3 forecasts
```

---

## Roadmap
- [ ] Cloud deployment (backend + managed Postgres)
- [ ] Authentication / user roles
- [ ] Automated alerts (email / mobile) on critical thresholds
- [ ] Extension to other West African basins

---

*Water monitoring project — real satellite data, explainable AI.*
