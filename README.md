# 💧 WaterTracker Africa — Satellite monitoring of water resources

> Monitoring of small reservoirs in West Africa (Burkina Faso) from **real satellite data (Google Earth Engine)**: monthly water surface at **10 m**, **machine-learning forecasts** of reservoir filling 1-3 months ahead, **early warning** of critical levels and a **drying-month forecast** for the dry season.

![Stack](https://img.shields.io/badge/Front-React%20%2B%20TypeScript-61dafb) ![Stack](https://img.shields.io/badge/Back-FastAPI%20%2B%20Python-009688) ![Stack](https://img.shields.io/badge/DB-PostgreSQL%20%2B%20PostGIS-336791) ![Stack](https://img.shields.io/badge/ML-RandomForest%20%2B%20Prophet-ff69b4)

---

## Overview

WaterTracker monitors a network of **water points** (dams, reservoirs, ponds) around Ouagadougou. The pipeline ingests satellite imagery, measures the water surface of each reservoir every month, forecasts its filling, and exposes everything through an API and an interactive map.

### Why it exists
Small reservoirs carry the dry season around Ouagadougou: livestock watering, market gardening and, in places, domestic water. Apart from the large dams that supply the city, none of them is gauged, so managers usually learn that a reservoir has dried up after the fact. WaterTracker uses free satellite archives to measure every reservoir every month and to anticipate the dry-season drawdown.

### What the system does

**1. Reservoir inventory (GIS)**
- The application's 65 water points are linked to their physical water body: 44 reservoirs, since several points can share one dam.
- The inventory was checked against the JRC Global Surface Water map: it covered 76 % of the water area but only 38 % of the water bodies of 10 ha or more. The 56 missing ones were added, giving 100 water bodies analysed, 96 of them modelled.
- Each added water body starts as "to validate"; a manager can confirm or reject it through the API.

**2. Monthly satellite measurement at 10 m**
- Water area of each reservoir every month since January 2019, from Sentinel-2 (MNDWI with the SWIR band sharpened to 10 m).
- Clouds are masked pixel by pixel with Cloud Score+, so 98.7 % of reservoir-months are observed directly; Sentinel-1 radar fills the cloudy months.
- Every value keeps its source (optical, radar, interpolated) for traceability.
- An indicative volume is estimated with a regional area-volume relationship (valid for reservoirs of 1 to 35 ha).
- Rainfall (CHIRPS) and evaporation, temperature and soil moisture (ERA5-Land) are attached to each reservoir's sub-basin.

**3. Filling forecast, 1 to 3 months ahead**
- A random forest forecasts each reservoir's filling ratio (water area divided by its reference area), with a calibrated 80 % interval.
- On the test years (2025-2026) it is 19.6 % more accurate than the reservoir's seasonal normal one month ahead; at two and three months it only matches the seasonal normal, and even perfect rainfall knowledge would not change that.

**4. Early warning of a critical level**
- Probability that a reservoir falls below 20 % of its reference area, translated into statuses on the map: active, at risk, dried up.
- On the test years, it flags 70-80 % of the reservoirs that will enter a critical state, and 83-90 % of its alerts are confirmed.

**5. Drying month (dry season)** — *in the API and the bulletin from October to March*
- For forecasts issued from October to March: the most likely month in which each reservoir will fall below its critical level, an 80 % range, and the probability that it lasts until the rains return at the end of June.
- A reservoir's usual drying month is already right within one month in 94 % of cases; the survival model refines it, mostly for forecasts issued from November to January and in unusual years (`backend/ml/drying.py`).

**6. Monthly bulletin, map and reservoir sheets**
- Bulletin of all reservoirs ranked by risk (JSON, CSV, print).
- Interactive map with filters by zone and status, a sheet per reservoir (measured filling, history, forecast, range), and a route to the water point (OpenRouteService).

**7. Automatic monthly update** — *ready, to be switched on with the GitHub settings*
- A GitHub Actions workflow runs every week, outside the API (the free hosting plan sleeps). It finds the latest month published by ERA5-Land and CHIRPS, collects every month missing since the last one in the database, oldest first, measures every reservoir in Google Earth Engine, issues the forecasts of each month and updates the statuses.
- Each month is saved as soon as it is collected, and poorly measured months (persistent clouds) are reported.
- Alerts: a failed run, or data more than two months behind, opens a GitHub issue that closes itself at the next successful run; `/api/health` reports the latest month and the delay.
- To switch it on: publish the model bundle in a GitHub release and add the database URL and an Earth Engine service-account key to the repository's Actions settings (`backend/README.md`, "Automatic monthly update"). Models are still retrained manually, once a year after the rainy season.

**8. Legacy features (v2)**
- Prophet drying-up curve, text advice generated by an LLM (Groq / Qwen) and a historical NDWI report. The audit of the v2 model showed that its outputs are not reliable; the advice is to be rebuilt on the v3 forecasts.

**9. Research and documentation**
- Reproducible notebooks in English: the full pipeline from Earth Engine to the forecasting model, and the drying-month analysis.
- Honest evaluation (temporal validation, strong baselines, significance tests), model card, unit tests, and an Independent Project report (`docs/independent-project/`).

### AI components: status

| Component | What it does | Status |
|---|---|---|
| Filling forecast (random forest) | Filling ratio 1-3 months ahead, 80 % interval | Done, served by the API |
| Early warning (gradient-boosting classifier) | Probability of a critical level, map statuses | Done, served by the API |
| Drying month (survival model) | Most likely critical month, range, probability of lasting until June | Done, served by the API and shown in the bulletin and the reservoir sheet from October to March |
| Water detection pixel by pixel (U-Net) | Better measurement of ponds under 5 ha and of water under vegetation | First model trained (12 epochs on CPU): on ambiguous pixels it beats the MNDWI rule, not yet Dynamic World (see below); not used in the monthly measurement yet |
| Automatic inventory | Detect every reservoir each year, to scale to a region or a country | Code ready (`ml/unet_inventory.py`); not run yet, needs Earth Engine |
| Abnormal withdrawals | Compare the observed drawdown with the drawdown expected from comparable reservoirs, flag reservoirs that empty much faster | Analysis done (model, tests, notebook); low sensitivity, needs field checks; not in the API |

### U-Net water detection: first results

The current measurement classifies each pixel alone with a threshold (MNDWI > 0) and hesitates on shorelines, turbid or shallow water and aquatic vegetation. The U-Net sees each pixel's neighbourhood and six Sentinel-2 bands.

- **Data**: 1,768 Sentinel-2 chips of 128 × 128 pixels at 10 m, published in the [`unet-data-v1`](https://github.com/mysteriodataweb/waterTrack/releases/tag/unet-data-v1) release. Chips with no labelled pixel are left out, leaving 1,230 for training, 389 for validation and 118 for test (test chips come from blocks never seen in training).
- **Labels without manual work**: a pixel is "water" when both the MNDWI index and Dynamic World say so clearly, "land" when both clearly say no. Every other pixel is ignored in training: those are the ambiguous cases the network has to learn to handle.
- **Training**: 12 epochs on CPU (about 64 s each), best validation IoU 0.9995 at epoch 11.

**Results on the 118 test chips** (`backend/ml/unet_results/metrics_test.json`):

| Method | IoU on labelled pixels | Ambiguous pixels: radar-dark among "water" | Radar-dark among "land" | Separation | Water area |
|---|---|---|---|---|---|
| MNDWI > 0 rule (current) | 1.000 | 49.6 % | 16.9 % | 0.33 | 808 ha |
| **U-Net** | 0.998 | 56.2 % | **9.1 %** | **0.47** | 919 ha |
| Dynamic World | 1.000 | 67.7 % | 14.7 % | **0.53** | 742 ha |

How to read it:
- **The IoU on labelled pixels is not informative**: those pixels are the obvious cases, and the two references score 1.000 because the labels come from them. It only shows that the U-Net reproduces the easy cases.
- **The real test is the 6.4 % of ambiguous pixels**, judged with Sentinel-1 radar, which the network never saw: open water is dark on radar. A good map puts many radar-dark pixels in "water" and few in "land"; the separation is the difference between the two shares.
- **The U-Net clearly beats the current rule** on ambiguous pixels (0.47 vs 0.33). Where they disagree, the radar mostly sides with the U-Net: 64 % of the 13,436 pixels it calls water and the rule calls land are radar-dark, against 17 % of the 2,289 pixels the rule calls water and the U-Net rejects.
- **It is still behind Dynamic World** (0.47 vs 0.53). It misses the least water (lowest share of radar-dark pixels left in "land"), but it also adds water the radar does not confirm, hence a larger water area.
- **Limits**: radar is not ground truth (wind brightens water; dry sandy soils and smooth surfaces look dark; vegetated water looks brighter), so these figures show a direction, not an accuracy. This is a short CPU run; the full 40-epoch training on GPU (`backend/notebooks/WaterTracker_unet_colab.ipynb`) may close the gap with Dynamic World.

Training guide and how to retrieve the model: `backend/ml/UNET_TRAINING.md`.

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
| Monthly update | GitHub Actions workflow (`.github/workflows/monthly-update.yml`) + `scripts/monthly_update.py` (`app/collectors/monthly.py`) |
| In-process scheduler (optional) | APScheduler (`app/collectors/scheduler.py`) |

### Research notebooks — `backend/notebooks/`
- `WaterTracker_pipeline.ipynb`: complete, reproducible pipeline from Google Earth Engine extraction
  (Sentinel-2 at 10 m + Sentinel-1, CHIRPS, ERA5-Land) to the filling-ratio forecasting model
  (temporal validation, calibrated intervals, model card).
- `WaterTracker_drying_date.ipynb`: drying-month model for the dry season, built on the monthly panel
  (`backend/data/gee/panel_monthly.parquet`), no Earth Engine access needed.
- `WaterTracker_withdrawals.ipynb`: reservoirs that lose water faster than expected in the dry season,
  on the same panel, validated by injecting simulated withdrawals.

See `backend/README.md`.

### Independent Project — `docs/independent-project/`
Report (Word and PDF) written to the TamTam Digital School guidelines, with its sources, English
figures, build scripts and defense preparation. The technical report of the backend is `docs/independent-project/technical_report_backend.md`.

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
| `GET` | `/api/water-sources/{id}/forecast`, `/api/reservoirs/{id}/forecast` | v3 filling-ratio forecast 1-3 months ahead (interval, probability of critical level) |
| `GET` | `/api/reservoirs/{id}/drying` | v3 dry season (October to March): month of the critical level, 80 % range, probability of lasting until June |
| `GET` | `/api/bulletin` | v3 monthly bulletin: all reservoirs ranked by risk, with the drying month in the dry season (JSON or CSV) |
| `GET` | `/api/reservoirs`, `/api/reservoirs/{id}/history` | v3 reservoirs and their monthly water-surface series (10 m) |
| `GET` | `/api/report/summary` | Aggregated historical report (NDWI trend, zones, top risk) |
| `GET` | `/api/health` | Service health and data freshness (latest month, months behind) |
| `POST` | `/api/admin/monthly-update` | Collect a month, or catch up the missing months, then forecast and update statuses (API key) |
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

## Monthly update (data collection)

The data must stay current for the bulletin, the alerts and the drying month to mean anything. Collection is automated by a GitHub Actions workflow, separate from the API.

**How it works**
1. Every Monday (and on demand from the Actions tab), the workflow looks for the latest month published by both ERA5-Land (evaporation, temperature) and CHIRPS (rainfall); CHIRPS comes out about three weeks after the end of the month.
2. It collects every month missing since the last one in the database, oldest first, at most 6 per run: water area at 10 m (Sentinel-2, radar for cloudy months) and climate of each modelled reservoir.
3. Each month is saved as soon as it is collected, then the forecasts, statuses and, from October to March, the drying month are issued for it.
4. A month where more than 25 % of the reservoirs could not be measured is flagged as a warning on the run page.

**Alerts**
- A failed run, or data still more than two months behind after the run, opens a GitHub issue "Monthly update failed" with a link to the run; it is closed at the next successful run.
- `GET /api/health` reports the latest month in the database and how many months behind it is (`data: stale`, `status: degraded` beyond two months), which also reveals a workflow that has stopped running.

**Switching it on** (once, details in `backend/README.md`, "Automatic monthly update")
1. Publish the model bundle (`backend/ml/runs/forecast_latest/bundle.joblib`) in a GitHub release and note its SHA-256 fingerprint; the update refuses a bundle whose fingerprint differs.
2. Create an Earth Engine service account and download its JSON key.
3. In Settings > Secrets and variables > Actions, add the secrets `DATABASE_URL` and `GEE_SERVICE_ACCOUNT_KEY`, and the variables `MODEL_BUNDLE_URL` and `MODEL_BUNDLE_SHA256`.
4. Run the workflow once by hand (Actions > Monthly update > Run workflow).

Until these are set, the weekly run only prints a notice. The same update runs anywhere with the same environment variables:

```bash
cd backend
python -m scripts.monthly_update                      # catch up every missing month
python -m scripts.monthly_update --month 2026-10 --force
```

GitHub pauses scheduled workflows of a public repository after 60 days without activity; re-enable it in the Actions tab.

---

## Requirements
- Python 3.11+, Node 20+
- Accounts: **Google Earth Engine**, **Groq** (LLM), **OpenRouteService** (navigation)
- PostgreSQL database with the PostGIS extension

---

## Tests
```bash
cd backend
pytest -q          # API, predictions, fixes, feature leakage checks, v3 forecasts, drying month, monthly update
```

---

## Roadmap
- [x] Cloud deployment configuration (Render API, Neon PostgreSQL/PostGIS, Vercel frontend)
- [x] Drying-month model for the dry season (`backend/ml/drying.py`)
- [x] Serve the drying month in the API and the monthly bulletin
- [x] Show the drying month in the frontend (reservoir sheet and bulletin table)
- [x] Reliable monthly collection: weekly GitHub Actions trigger, catch-up of missed months, failure alerts (to switch on: `backend/README.md`)
- [ ] Annual retraining with a promotion check, and monthly verification of past forecasts
- [ ] Replace the legacy LLM advice with messages built on the v3 forecasts
- [x] Abnormal-withdrawal analysis (`backend/ml/withdrawals.py`): a short list of reservoirs to check
- [ ] Field checks of the flagged reservoirs, then serve the list in the API
- [x] First U-Net water-detection model (12 CPU epochs, results in `backend/ml/unet_results/`)
- [ ] Full U-Net training (40 epochs on GPU), then decide whether it replaces the MNDWI rule in the monthly measurement
- [ ] Run the automatic inventory with the U-Net and check the candidate water bodies
- [ ] Field validation with a partner (staff gauges, photos)
- [ ] Authentication / user roles
- [ ] Automated alerts (email / SMS) on critical thresholds
- [ ] Extension to other West African basins

---

*Water monitoring project — real satellite data, explainable AI.*
