# WaterTracker Backend v3

Monitoring and early-warning system for the reservoirs around Ouagadougou
(Burkina Faso), built on real satellite data (Google Earth Engine).

- **v3 (current)**: **monthly water surface at 10 m** for each water body (Sentinel-2,
  gap-filled with Sentinel-1), forecast of the **filling ratio 1-3 months ahead** with a
  prediction interval and the probability of reaching a critical level, **monthly
  bulletin**, automatic updates.
- **v2 (legacy, kept)**: half-yearly NDWI per water point, Prophet. Its LLM-written advice
  (Groq) is replaced by advice built on the v3 forecasts (`app/services/advice.py`).
  Still served by `/prediction`; the current map pages no longer call it.

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
│   ├── services/               # reservoirs (v3: panel, bulletin), advice (v3), ml, prophet, risk
│   └── collectors/             # water_area + monthly (v3), scheduler, earth_engine + ingest (v2)
├── ml/
│   ├── features.py             # v3: model features (shared by notebook and API)
│   ├── forecasting.py          # v3: inference (shared by notebook and API)
│   ├── drying.py               # dry-season drying month (survival model, baselines, bulletin)
│   ├── withdrawals.py          # abnormal losses: expected dry-season drop, chronic and episodic flags
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
copy .env.example .env                       # DATABASE_URL, API_KEY, ORS, GEE_PROJECT
earthengine authenticate                     # once, locally
uvicorn app.main:app --reload                # interactive docs: http://localhost:8000/docs
```

## v3 pipeline: from satellite to bulletin

| Step                                                                             | Command                                                                  | Frequency                                    |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | -------------------------------------------- |
| 1. Research: extraction 2019 -> today, analysis, training, model saved           | `notebooks/WaterTracker_pipeline.ipynb`                                  | once, then every year after the rainy season |
| 2. Database load: reservoirs, monthly surfaces, forecasts, water-point statuses  | `python -m scripts.load_v3`                                              | after each notebook run                      |
| 3. Monthly update: every month missing since the last one in the database, forecasts, statuses | GitHub Actions workflow `monthly-update.yml`, `python -m scripts.monthly_update` or `POST /api/admin/monthly-update` | every week (idempotent) |
| 4. Annual retraining with a promotion check | GitHub Actions workflow `retrain.yml` or `python -m scripts.retrain` | every year (1 December) |

The monthly update is **idempotent** and **catches up**: it looks for the latest month
published by both ERA5-Land and CHIRPS, then collects every month missing since the last
one in the database, oldest first (at most 6 per run; the rest waits for the next run).
Each month is saved as soon as it is collected, so a failure on one month does not lose the
previous ones, and forecasts are issued for each collected month. A month where more than
25 % of the reservoirs have no measurement (persistent clouds, unusable radar) is reported
as a warning. The forecasts issued earlier for the months just collected are then checked
against what was measured (`ml/verification.py`): error compared with the reservoir's
seasonal normal (median of the same calendar month in previous years), share of observations
inside the 80 % interval, alerts confirmed or not. The run summary shows it per horizon, and
`GET /api/verification` gives the record over the last 12 measured months. The extraction parameters in `app/collectors/water_area.py` are those of the
notebook (10 m, Cloud Score+ 0.60, 90 % reliability threshold); changing them would make new
measurements incomparable with the training data. Parity has been checked: the API
collector and the notebook give identical values for all 96 reservoirs.

## Endpoints

| Method | Path                                                   | Description                                                            | Auth    |
| ------ | ------------------------------------------------------ | ---------------------------------------------------------------------- | ------- |
| GET    | `/api/health`                                          | Database + external services status, data freshness (latest month, months behind; `stale` beyond 2) | no |
| GET    | `/api/reservoirs?origin=&validation=`                  | **v3** Water bodies: origin, validation, latest filling, status        | no      |
| GET    | `/api/reservoirs/{id}/history?start=&end=`             | **v3** Monthly series: surface, filling, data source, volume, rainfall | no      |
| GET    | `/api/reservoirs/{id}/forecast`                        | **v3** 1-3 month forecast: filling, 80 % interval, P(critical level)   | no      |
| GET    | `/api/water-sources/{id}/forecast`                     | **v3** Same forecast, through the application's water point            | no      |
| GET    | `/api/reservoirs/{id}/drying`                          | **v3** Dry season: month of the critical level, 80 % range, P(lasts to June) | no |
| GET    | `/api/bulletin?month=&format=json\|csv`                | **v3** Monthly bulletin, reservoirs ranked by risk, with alert level and one-line summary; CSV export | no |
| GET    | `/api/reservoirs/{id}/advice`                          | **v3** Advice for action for four audiences (see below)                | no      |
| GET    | `/api/verification?months=12`                          | **v3** Record of the forecasts already issued, once their target month is measured: error vs the seasonal normal, 80 % interval coverage, alerts | no |
| PATCH  | `/api/admin/reservoirs/{id}/validation`                | **v3** Inventory validation (`valide`, `rejete`, `a_valider`)          | API key |
| POST   | `/api/admin/monthly-update`                            | **v3** Collect `month`, or catch up the missing months (`max_months`, default 3) + forecasts + statuses | API key |
| POST   | `/api/admin/recompute`                                 | Water-point statuses (v3 if forecasts exist, otherwise v2)             | API key |
| GET    | `/api/water-sources?page=&zone=&status=`               | Paginated water points                                                 | no      |
| GET    | `/api/water-sources/{id}`                              | Water-point details                                                    | no      |
| GET    | `/api/water-sources/{id}/prediction`                   | v2: Prophet drying-up curve                                            | no      |
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

**Advice for action** (`app/services/advice.py`, `GET /api/reservoirs/{id}/advice`): fixed
rules turn the latest v3 forecast, and the drying month in the dry season, into advice for
four audiences: residents and users (`communaute`), field agent (`agent_terrain`), NGO
(`ong`) and government service (`gouvernement`). It replaces the v2 text written by an LLM
(Groq) from the half-yearly NDWI analysis, which the audit found unreliable. Every sentence
repeats a number of the forecast shown on the reservoir sheet, and the same situation
always gives the same advice.

| Level | When |
|---|---|
| `critique` | almost dry next month (status `tari`) |
| `alerte` | at least one chance in two of falling below the critical level next month (`à risque`), or already below it and staying there |
| `vigilance` | no alert next month, but a high risk at 2-3 months, a risk of at least 20 %, a reservoir still below the critical level that refills, or a drying month earlier than usual |
| `normal` | no alert within three months |

The response gives the level, a one-line summary, the facts with their numbers (measured
filling and change over a month, forecast with its 80 % range, drying month), the actions
for each audience, the deadline (relative to today, because the data lag one to two months
behind the calendar), caveats (data behind schedule, wide interval, water body not yet
confirmed in the field, satellite estimate to check on site) and, for each audience, the
whole message as text to copy or share. The bulletin carries the same level and summary
for every reservoir (`level`, `message`, also in the CSV).

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

### Drying month (dry season)

`notebooks/WaterTracker_drying_date.ipynb` answers "in which month will this reservoir
fall below its critical level, and will it last until the end of June?" for forecasts
issued from October to March. It reads `data/gee/panel_monthly.parquet` only (no Earth
Engine access needed) and uses `ml/drying.py`: a discrete-time survival model (logistic
and gradient-boosting hazards) compared with the reservoir's usual drying month, a
projection, a linear trend and a Kaplan-Meier reference, with a temporal split by season
(test: 2024-25 and 2025-26). `ml.drying.forecast_drying(model, panel, "YYYY-10", ref_seasons)`
returns the bulletin table: most likely month, 80 % range, probability of lasting until June.

In the API, the monthly update (and `scripts/load_v3.py`) calls `ml.drying.issue_bulletin`
when the issue month is between October and March. The model is fitted on the fly on the
seasons that ended before the issue month (a few seconds, no saved bundle), and the result
is stored in the `drying_forecasts` table, created at start-up. It is served by
`GET /api/reservoirs/{id}/drying` and in the `drying` field of each reservoir of
`GET /api/bulletin` (`drying_*` columns in the CSV). Outside the dry season, and for a
reservoir already below its critical level, there is no drying forecast.

### Abnormal withdrawals

`notebooks/WaterTracker_withdrawals.ipynb` asks which reservoirs lose water faster than
expected in the dry season. `ml/withdrawals.py` converts the water area into a level index
(Liebe et al., 2005), learns the expected monthly drop on the other reservoirs, and gives
two readings: reservoirs that are persistently faster than their peers, and seasons in
which a reservoir is faster than usual. There is no field record of withdrawals: a flag is
an unexplained loss to check, and the detector is validated by injecting simulated
withdrawals. Sensitivity is low (only losses that at least double the normal drop are
found, and most of those are still missed). Not served by the API.

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
3. Monthly update: see the next section.

## Automatic monthly update (GitHub Actions)

The update runs outside the API, in the workflow `.github/workflows/monthly-update.yml`:
every Monday, and on demand from the Actions tab (a month can be given, and forced).
It does not depend on Render, whose free plan puts the service to sleep, which would stop
an in-process scheduler.

**Setup, once:**

1. **Publish the model bundle.** It is excluded from git (`ml/runs/`). Attach it to a GitHub
   release and note its SHA-256 fingerprint:
   ```bash
   gh release create model-v3 ml/runs/forecast_latest/bundle.joblib --title "Forecasting model v3"
   sha256sum ml/runs/forecast_latest/bundle.joblib      # Windows: certutil -hashfile <file> SHA256
   ```
   The download URL is `https://github.com/<owner>/<repo>/releases/download/model-v3/bundle.joblib`.
   The bundle is a joblib (pickle) file, so the update refuses it unless its fingerprint is
   exactly `MODEL_BUNDLE_SHA256`. Publishing a new bundle means updating the fingerprint.
   On a public repository the release is public too: the bundle holds the trained models and
   per-reservoir statistics, no credentials.
2. **Earth Engine service account.** Create a service account in the Google Cloud project,
   register it for Earth Engine, and download its JSON key.
3. **GitHub settings** (Settings > Secrets and variables > Actions):
   - secrets: `DATABASE_URL` (the Neon connection string), `GEE_SERVICE_ACCOUNT_KEY` (the JSON key content);
   - variables: `MODEL_BUNDLE_URL`, `MODEL_BUNDLE_SHA256`, and `GEE_PROJECT` if it is not `water-492400`.
4. **First run:** Actions > Monthly update > Run workflow. Until the four values above are
   set, the workflow only prints a notice and does nothing.

**Alerts.** If a run fails, or if the data are still more than 2 months behind after it,
the workflow opens an issue "Monthly update failed" (or comments on the open one) with a
link to the run, and closes it at the next successful run. Each run page shows a summary:
months collected, data sources, warnings, forecasts issued. `GET /api/health` also reports
`data: stale` and `status: degraded` when the latest month is more than 2 months old, which
catches the case where the workflow stopped running altogether.

**Limits.** GitHub disables scheduled workflows in public repositories after 60 days without
any repository activity (it sends an e-mail first); re-enable it in the Actions tab.
The same update can run elsewhere with the same environment variables:
`python -m scripts.monthly_update` (exit code 0: success, 1: failure, 2: data still stale), or
on the server with `SCHEDULER_ENABLED=true` if the service stays awake.

## Annual retraining (with a promotion check)

Once a year, after the rainy season (1 December, workflow `.github/workflows/retrain.yml`,
or `python -m scripts.retrain`), the v3 model is retrained on the monthly panel of the
database, which grows every month. The model in service (the "champion") sets the
configuration: every estimator is cloned with the same hyperparameters and the same
formulation; only the data change. The reference areas, the radar calibration and the
static features stay those of the champion, so the filling ratio keeps its definition.

**Honest evaluation.** The new model (the "challenger") is trained only on the months before
the last season (the 12 latest target months), with its interval correction calibrated on
the year before, then forecasts that season and is scored like the forecasts actually
issued (`ml/verification.py`).

**Promotion check.** The candidate is proposed only if every check passes:

| Check | Threshold |
|---|---|
| 1 month ahead: gain over the seasonal normal | strictly positive |
| 2 and 3 months ahead: gain over the seasonal normal | at least −5 % (the champion only matches the normal there) |
| Share of observations inside the 80 % interval, each horizon | 70 % to 90 % |
| Error compared with the champion's real record on the same forecasts (when at least 200 issued forecasts have been verified for that horizon) | at most 2 % worse |

The candidate itself is then trained on all the data, season included, and written with
`model_card.json` and `report.md` (decision, scores, checks, SHA-256 fingerprint). The
workflow uploads them as the run artefact `retrained-model` and opens an issue with the
decision. Exit code of the script: 0 candidate ready, 2 champion kept, 1 failure.

**Putting a candidate in service** stays a human decision: download the artefact, publish
`bundle.joblib` in a new release, then update the variables `MODEL_BUNDLE_URL` and
`MODEL_BUNDLE_SHA256`. The next monthly update uses it; its forecasts carry the new
`model_version`, so the verification keeps the records of the two models apart.

Offline, without the database (and therefore without the champion's real record):
`python -m scripts.retrain --panel data/gee/panel_monthly.parquet`. A trial on the
monthly panel (96 reservoirs, evaluation season September 2025 to August 2026) with the
notebook's configuration takes about 3 minutes on 4 CPU cores.

## Tests

```bash
pytest -q
```

Unit tests (S2/S1 fusion, features without temporal leakage, v2 fixes, bulletin, monthly
update: catch-up, quality warnings, bundle fingerprint, exit codes; forecast verification;
retraining: evaluation window, no leakage, promotion check, candidate served by the inference;
advice: level of each situation, numbers repeated, deadlines, caveats, bulletin) and API
integration tests on the local database (skipped automatically when v3 data is missing).

## Security

- `.env` is never committed; a strong API key is required in production (constant-time comparison).
- All write endpoints (`/admin/*`, `/predict`) require `X-API-Key`.
- Outgoing calls verify TLS (system certificates through `truststore`).
