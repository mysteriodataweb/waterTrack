# WaterTracker Backend — Technical Report

*Updated October 2026. This report replaces an earlier version written for the v2 backend; most of the problems that version listed have since been fixed (see "Status of the earlier findings" below). It is the technical companion of the Independent Project report in `docs/independent-project/`.*

## 1. Purpose

The backend serves the WaterTracker application: an inventory of water points around Ouagadougou (Burkina Faso), the monthly water area of each reservoir measured by satellite, and forecasts of each reservoir's filling ratio one to three months ahead, with an early-warning status. It also provides routing to a water point and a historical summary report.

## 2. Architecture

| Layer | Technology | Location |
|---|---|---|
| API | FastAPI + Pydantic v2, single router under `/api` | `backend/app/main.py`, `app/router.py`, `app/routes/` |
| Database | PostgreSQL + PostGIS (SQLAlchemy, pg8000), hosted on Neon | `app/database.py`, `app/models.py` |
| Satellite collection | Google Earth Engine (Sentinel-2, Sentinel-1, CHIRPS, ERA5-Land) | `app/collectors/water_area.py`, `monthly.py` |
| Scheduler | APScheduler, idempotent monthly update | `app/collectors/scheduler.py` |
| Forecasting (v3) | scikit-learn bundle trained in the research notebook | `ml/features.py`, `ml/forecasting.py`, `notebooks/` |
| Legacy forecasting (v2) | Prophet drying-up date, half-yearly NDWI | `app/services/prophet_service.py`, `ml/train.py` |
| Text recommendations | Groq LLM, with a rule-based fallback | `app/services/llm.py`, `recommande.py` |
| Routing | OpenRouteService, with Photon as reverse-geocoding fallback | `app/routes/navigation.py` |
| Deployment | Render (API, `render.yaml`), Vercel (frontend) | repository root |

The research notebook and the API share the same feature code (`ml/features.py`) and the same inference function (`ml/forecasting.py`), so the model evaluated in the notebook is exactly the one the API runs.

## 3. Data model

- **v3**: `Reservoir` (physical water body: origin `application` or `JRC`, analysis region, reference area, validation status), `ReservoirSource` (link between application water points and reservoirs), `WaterAreaObservation` (one row per reservoir and month: area, filling ratio, data source `S2` / `S1` / `interp` / `manquant`, volume, rainfall), `FillForecast` (forecast per reservoir, issue month and horizon, with 80 % interval and probability of a critical level).
- **v2 (kept)**: `WaterSource` (the 65 application water points, PostGIS geometry, status) and `NdwiObservation` (half-yearly NDWI).

The statuses `actif` / `à risque` / `tari` and the source label `manquant` are kept in French because the frontend and the database already use them.

## 4. Endpoints

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/api/health` | Database and external-service status | no |
| GET | `/api/reservoirs` | Water bodies: origin, validation, latest filling, status | no |
| GET | `/api/reservoirs/{id}/history` | Monthly series: area, filling, data source, volume, rainfall | no |
| GET | `/api/reservoirs/{id}/forecast` | 1-3 month forecast, 80 % interval, probability of a critical level | no |
| GET | `/api/water-sources/{id}/forecast` | Same forecast through an application water point | no |
| GET | `/api/bulletin?month=&format=json\|csv` | Monthly bulletin ranked by risk | no |
| PATCH | `/api/admin/reservoirs/{id}/validation` | Inventory validation (`valide`, `rejete`, `a_valider`) | API key |
| POST | `/api/admin/monthly-update` | Collect one month, forecast, update statuses | API key |
| POST | `/api/admin/recompute` | Recompute water-point statuses | API key |
| GET | `/api/water-sources`, `/api/water-sources/{id}` | Paginated water points, details | no |
| GET | `/api/water-sources/{id}/prediction` | v2 Prophet drying-up forecast + text recommendation | no |
| POST | `/api/predict`, `/api/admin/collect` | v2 prediction and half-yearly collection | API key |
| GET | `/api/report/summary` | Aggregated historical report | no |
| POST / GET | `/api/navigation/route`, `/api/navigation/reverse` | Routing, reverse geocoding | no |

## 5. The v3 monthly pipeline

1. **Research run** (`notebooks/WaterTracker_pipeline.ipynb`, once a year after the rainy season): extraction since 2019, quality control, training, evaluation, bundle and model card in `ml/runs/forecast_latest/`.
2. **Database load** (`python -m scripts.load_v3`): reservoirs, monthly areas, forecasts, statuses.
3. **Monthly update** (scheduler or `POST /api/admin/monthly-update`): collects the latest month published by ERA5-Land and CHIRPS with the notebook's exact extraction parameters, issues forecasts and updates statuses. It is idempotent.

Status rules: `tari` if the 1-month forecast filling is below 5 %; `à risque` if the probability of falling below 20 % of the reference area is at least 50 %; `actif` otherwise; `inconnu` for water points whose reservoir is not modelled.

## 6. Model performance (test period 2025 to August 2026)

| Horizon | Random forest MAE | Climatology MAE | Skill | Significance | 80 % interval coverage |
|---|---|---|---|---|---|
| 1 month | 0.108 | 0.134 | +19.6 % | p < 0.001 | 83 % |
| 2 months | 0.133 | 0.134 | +0.9 % | p = 0.41 | 80 % |
| 3 months | 0.130 | 0.134 | +3.4 % | p = 0.11 | 75 % |

The alert classifier reaches ROC-AUC 0.96-0.97 and detects 70-80 % of entries into a critical state with 83-90 % precision. Full results: Independent Project report, section 4.

## 7. Quality, testing and security

- **Tests**: 39 tests in `backend/tests/` (API, v2 fixes, feature leakage checks, S2/S1 fusion, v3 forecasts); integration tests are skipped automatically when the v3 data are missing. Run with `pytest -q` in `backend/`.
- **Validation**: Pydantic schemas for requests and responses (`app/schemas.py`); paginated listings.
- **Secrets**: `.env` is ignored by git; on Render, secrets are set in the service environment (`sync: false` in `render.yaml`).
- **Write endpoints**: protected by `X-API-Key`, compared in constant time.
- **CORS**: restricted to the origins listed in `CORS_ORIGINS`, optionally a pattern in `CORS_ORIGIN_REGEX`.
- **TLS**: outgoing calls verify certificates through the system store (`truststore`).
- **Reproducibility**: fixed seed, cached extractions, panel fingerprint and library versions in the model card, reload check of the saved bundle.

## 8. Status of the earlier findings

| Earlier finding (v2 report) | Status |
|---|---|
| API keys in a committed `.env` | Fixed: `.env` ignored, secrets in the host environment |
| CORS open to all origins | Fixed: configurable allow-list |
| No authentication | Fixed for write endpoints (API key) |
| Empty `schemas.py`, no input validation | Fixed: Pydantic schemas |
| `gemini.py` misnamed | Fixed: `app/services/llm.py` |
| Scripts at the root, absolute Windows paths | Fixed: `scripts/`, `ml/`, relative paths |
| No tests, no health check, no pagination | Fixed |
| N+1 queries on `/water-sources` | Fixed |
| Naive drying-up probability, default coordinates, model trained on a few hundred rows | Superseded by v3 (monthly satellite series, honest evaluation); the v2 audit is in the notebook, section 6 |
| Inference bug (scaling applied to an unscaled model) | Found by the audit and fixed in `app/services/ml.py` |
| No automatic collection | Fixed: Earth Engine collector and scheduler |

## 9. Remaining limitations and recommendations

1. **Default API key opens the write endpoints.** If `API_KEY` is not set, `app/deps.py` accepts every call (development mode, with a warning). Recommendation: refuse to start in production without a strong key.
2. **Public endpoints that spend paid or rate-limited quotas.** `/navigation/*` (OpenRouteService) and `/water-sources/{id}/prediction` (Groq LLM) have no rate limiting. Recommendation: add rate limiting or cache the responses.
3. **Text recommendations still built on v2 outputs.** The LLM advice uses the Prophet drying-up date and the point NDWI, which the audit showed to be unreliable. Recommendation: replace them with short rule-based messages derived from the v3 forecast.
4. **Monthly update needs the model bundle and an Earth Engine service account on the server.** The bundle is excluded from git; it must be provided to the service, and the scheduler stays disabled (`SCHEDULER_ENABLED=false` in `render.yaml`) until then.
5. **Google Earth Engine licensing.** Earth Engine is free for research and non-commercial use; a paid service would need a commercial licence.
6. **Missing alert baseline.** A calendar-only alert rule should be evaluated before claiming that the classifier adds value beyond the season.
7. **Retire v2.** Once the frontend relies only on v3, the Prophet and half-yearly NDWI code can be removed to reduce maintenance.
