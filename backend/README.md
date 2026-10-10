# WaterTracker Backend v3

Monitoring and early-warning system for the reservoirs around Ouagadougou
(Burkina Faso), built on real satellite data (Google Earth Engine).

- **v3 (current)**: **monthly water surface at 10 m** for each water body (Sentinel-2,
  gap-filled with Sentinel-1), forecast of the **filling ratio 1-3 months ahead** with a
  prediction interval and the probability of reaching a critical level, **monthly
  bulletin**, automatic updates.
- **v2 (legacy, kept)**: half-yearly NDWI per water point, Prophet, Groq recommendations.
  Still served by `/prediction` (used by the current map).

---

## Architecture

```
backend/
├── app/
│   ├── main.py                 # FastAPI, CORS, system TLS certificates, scheduler
│   ├── config.py               # .env configuration (pydantic-settings)
│   ├── tls.py                  # truststore: system certificates (HTTPS-inspecting antivirus on Windows)
│   ├── database.py             # SQLAlchemy + PostgreSQL/PostGIS
│   ├── models.py               # v2: WaterSource, NdwiObservation
│   │                           # v3: Reservoir, ReservoirSource, WaterAreaObservation, FillForecast
│   ├── schemas.py              # Pydantic schemas (requests + responses)
│   ├── deps.py                 # API key (write endpoints)
│   ├── routes/                 # water, prediction, navigation, report, health, reservoirs (v3)
│   ├── services/               # reservoirs (v3: panel, bulletin), ml, prophet, risk, llm, recommande
│   └── collectors/             # water_area + monthly (v3), scheduler, earth_engine + ingest (v2)
├── ml/
│   ├── features.py             # v3: model features (shared by notebook and API)
│   ├── forecasting.py          # v3: inference (shared by notebook and API)
│   ├── train.py, evaluate.py   # v2 (legacy)
│   └── runs/                   # forecast_latest/bundle.joblib (v3), latest/ (v2)
├── notebooks/                  # WaterTracker_pipeline.ipynb: GEE -> v3 model (research paper)
├── scripts/                    # load_v3 (notebook results -> database), backfill_*, sync_water_geometries
├── tests/                      # unit tests + integration tests on the local database
└── reports/figures/            # paper figures (300 dpi)
```

## Getting started

```bash
python -m venv venv
venv\Scripts\activate                       # Windows
pip install -r requirements.txt
copy .env.example .env                       # DATABASE_URL, API_KEY, GROQ, ORS, GEE_PROJECT
earthengine authenticate                     # once, locally
uvicorn app.main:app --reload                # interactive docs: http://localhost:8000/docs
```

## v3 pipeline: from satellite to bulletin

| Step                                                                             | Command                                                                  | Frequency                                    |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | -------------------------------------------- |
| 1. Research: extraction 2019 -> today, analysis, training, model saved           | `notebooks/WaterTracker_pipeline.ipynb`                                  | once, then every year after the rainy season |
| 2. Database load: reservoirs, monthly surfaces, forecasts, water-point statuses  | `python -m scripts.load_v3`                                              | after each notebook run                      |
| 3. Monthly update: collection of the latest published month, forecasts, statuses | automatic (`SCHEDULER_ENABLED=true`) or `POST /api/admin/monthly-update` | every month                                  |

The monthly update is **idempotent**: the scheduler checks it every `COLLECT_HOURS` hours
and collects a month only once, as soon as ERA5-Land and CHIRPS have published it. The
extraction parameters in `app/collectors/water_area.py` are those of the notebook (10 m,
Cloud Score+ 0.60, 90 % reliability threshold); changing them would make new
measurements incomparable with the training data. Parity has been checked: the API
collector and the notebook give identical values for all 96 reservoirs.

## Endpoints

| Method | Path                                                   | Description                                                            | Auth    |
| ------ | ------------------------------------------------------ | ---------------------------------------------------------------------- | ------- |
| GET    | `/api/health`                                          | Database + external services status                                    | no      |
| GET    | `/api/reservoirs?origin=&validation=`                  | **v3** Water bodies: origin, validation, latest filling, status        | no      |
| GET    | `/api/reservoirs/{id}/history?start=&end=`             | **v3** Monthly series: surface, filling, data source, volume, rainfall | no      |
| GET    | `/api/reservoirs/{id}/forecast`                        | **v3** 1-3 month forecast: filling, 80 % interval, P(critical level)   | no      |
| GET    | `/api/water-sources/{id}/forecast`                     | **v3** Same forecast, through the application's water point            | no      |
| GET    | `/api/bulletin?month=&format=json\|csv`                | **v3** Monthly bulletin, reservoirs ranked by risk; CSV export         | no      |
| PATCH  | `/api/admin/reservoirs/{id}/validation`                | **v3** Inventory validation (`valide`, `rejete`, `a_valider`)          | API key |
| POST   | `/api/admin/monthly-update`                            | **v3** Collect one month + forecasts + statuses                        | API key |
| POST   | `/api/admin/recompute`                                 | Water-point statuses (v3 if forecasts exist, otherwise v2)             | API key |
| GET    | `/api/water-sources?page=&zone=&status=`               | Paginated water points                                                 | no      |
| GET    | `/api/water-sources/{id}`                              | Water-point details                                                    | no      |
| GET    | `/api/water-sources/{id}/prediction?profil=`           | v2: Prophet drying-up forecast + Groq recommendation                   | no      |
| POST   | `/api/predict`                                         | v2: periods until drying up                                            | API key |
| POST   | `/api/admin/collect`                                   | v2: half-yearly NDWI collection                                        | API key |
| GET    | `/api/report/summary`                                  | Aggregated report                                                      | no      |
| POST   | `/api/navigation/route`, GET `/api/navigation/reverse` | Routing, reverse geocoding                                             | no      |

**v3 statuses** (`ml/forecasting.py`): `tari` (dry) if the 1-month forecast filling is
< 5 %, `à risque` (at risk) if the probability of falling below the critical threshold
(`CRITICAL_FILL`, 20 % of the reference surface) is ≥ 50 %, otherwise `actif` (active).
They are copied onto the application's water points, so the current map shows them
without any frontend change. Water points whose reservoir is not modelled (no water ever
detected by satellite) are set to `inconnu` (unknown).

**Inventory**: the application's water points are linked to their physical water body
(several points can share one reservoir). Water bodies added from JRC (`origin = JRC`)
start as `a_valider` (to validate); a `rejete` (rejected) water body is left out of the
bulletin. Status and validation values are kept in French because the API and the
frontend already use them.

## Research notebook

`notebooks/WaterTracker_pipeline.ipynb` gathers the whole pipeline, documented
for a research paper: quality-controlled GIS inventory, water surface at 10 m (sharpened
MNDWI, native-10 m NDWI check, 10 m vs 20 m effect), Sentinel-2/Sentinel-1 fusion,
CHIRPS/ERA5-Land forcings, hydrological analysis, audit of the v2 model, forecasting with
temporal validation, conformal intervals, probabilistic alerts, spatial generalisation,
indicative volume, "oracle" experiment on the value of rainfall forecasts, table of
limitations.

```bash
pip install -r requirements.txt -r requirements-notebook.txt
python -m ipykernel install --user --name watertracker
cd notebooks && jupyter lab        # kernel "Python (WaterTracker)"
```

Outputs: `data/gee/` (Parquet cache, panel, inventory), `reports/figures/`,
`ml/runs/forecast_<date>/` and `ml/runs/forecast_latest/` (`bundle.joblib`, `model_card.json`).
The full 10 m extraction takes about 1 hour (parallel requests); later runs reuse the cache.

## Deployment (Render + Neon)

The API runs on Render; the PostgreSQL/PostGIS database is hosted on Neon. Paste the
connection string given by Neon as `DATABASE_URL` (locally in `.env`, on Render in the
service environment): its `sslmode` / `channel_binding` options are handled by the app.

To rebuild an empty database (new host, lost database):

```bash
python -m scripts.restore_sources   # water points from data/water_sources.json + NDWI history (Earth Engine, ~30 min)
python -m scripts.load_v3           # reservoirs, monthly surfaces, forecasts
```

`scripts.copy_database` copies everything from another PostgreSQL database instead, when
the old one is still reachable (`SOURCE_DATABASE_URL`).

1. Database: run `python -m scripts.load_v3` with `DATABASE_URL` pointing to the
   production database (v3 tables are created automatically, v2 tables are untouched).
2. Read-only use (bulletin, forecasts): nothing else to do, everything is served from
   the database.
3. Monthly update on the server: provide `ml/runs/forecast_latest/bundle.joblib` to the
   service (model artefacts are excluded from git) and an Earth Engine service account
   (`GEE_SERVICE_ACCOUNT_KEY`), then set `SCHEDULER_ENABLED=true`.

## Tests

```bash
pytest -q
```

Unit tests (S2/S1 fusion, features without temporal leakage, v2 fixes, bulletin) and API
integration tests on the local database (skipped automatically when v3 data is missing).

## Security

- `.env` is never committed; a strong API key is required in production (constant-time comparison).
- All write endpoints (`/admin/*`, `/predict`) require `X-API-Key`.
- Outgoing calls verify TLS (system certificates through `truststore`).
