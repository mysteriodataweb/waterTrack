"""
Charge en base les résultats du notebook (modèle v3). Idempotent.

  1. réservoirs physiques (géométrie, zone d'analyse, bassin, A_ref) + liens sources ;
  2. surfaces en eau mensuelles 2019 -> dernier mois (panel nettoyé) ;
  3. prévisions 1-3 mois émises au dernier mois, avec le paquet de modèles ;
  4. report de la prévision à 1 mois sur les sources de l'application.

Prérequis : avoir exécuté `notebooks/WaterTracker_pipeline.ipynb` (produit
`data/gee/*` et `ml/runs/forecast_latest/bundle.joblib`).

Usage :
  python -m scripts.load_v3             # tout charger
  python -m scripts.load_v3 --dry-run   # vérifier les fichiers sans écrire
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("load_v3")

import pandas as pd
from sqlalchemy import select, text

from app.database import SessionLocal, create_all
from app.models import ReservoirSource, WaterSource
from app.services import reservoirs as svc
from ml.forecasting import forecast, load_bundle

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "gee"


def read_features(path: Path) -> dict[str, dict]:
    """GeoJSON -> {reservoir_id: feature}."""
    feats = json.loads(path.read_text(encoding="utf-8"))["features"]
    return {f["properties"]["reservoir_id"]: f for f in feats}


def load_inputs() -> tuple[dict, dict, pd.DataFrame, dict]:
    for name in ("reservoirs.geojson", "analysis_regions.geojson", "panel_monthly.parquet"):
        if not (DATA_DIR / name).exists():
            raise FileNotFoundError(f"{DATA_DIR / name} manquant : exécuter le notebook")
    reservoirs = read_features(DATA_DIR / "reservoirs.geojson")
    regions = read_features(DATA_DIR / "analysis_regions.geojson")
    panel = pd.read_parquet(DATA_DIR / "panel_monthly.parquet")
    bundle = load_bundle()
    return reservoirs, regions, panel, bundle


def upsert_reservoirs(db, reservoirs: dict, regions: dict, bundle: dict) -> int:
    modelable = set(bundle["static"].index)
    a_ref = bundle["a_ref_ha"]
    stmt = text("""
        INSERT INTO reservoirs (id, origin, geometry, region, region_type, hybas_id, a_ref_ha, modelable, validation, created_at)
        VALUES (:id, :origin, ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326), ST_SetSRID(ST_GeomFromGeoJSON(:region), 4326),
                :region_type, :hybas_id, :a_ref, :modelable, :validation, now())
        ON CONFLICT (id) DO UPDATE SET
            origin = EXCLUDED.origin, geometry = EXCLUDED.geometry, region = EXCLUDED.region,
            region_type = EXCLUDED.region_type, hybas_id = EXCLUDED.hybas_id,
            a_ref_ha = EXCLUDED.a_ref_ha, modelable = EXCLUDED.modelable
    """)  # la validation saisie par le gestionnaire n'est jamais écrasée
    for rid, feat in reservoirs.items():
        p = feat["properties"]
        ref = a_ref.get(rid)
        db.execute(stmt, {
            "id": rid,
            "origin": p["origin"],
            "geom": json.dumps(feat["geometry"]),
            "region": json.dumps(regions[rid]["geometry"]),
            "region_type": p.get("region_type"),
            "hybas_id": None if p.get("hybas_id") is None else int(p["hybas_id"]),
            "a_ref": None if ref is None or pd.isna(ref) else float(ref),
            "modelable": rid in modelable,
            # Les sources de l'application sont validées de fait ; les ajouts JRC sont à valider
            "validation": "valide" if p["origin"] == "application" else "a_valider",
        })
    return len(reservoirs)


def upsert_links(db, reservoirs: dict) -> int:
    existing = set(db.execute(select(WaterSource.id)).scalars())
    db.execute(text("DELETE FROM reservoir_sources"))
    n = 0
    for rid, feat in reservoirs.items():
        ids = [int(x) for x in str(feat["properties"].get("source_ids") or "").split(",") if x.strip()]
        for sid in ids:
            if sid in existing:
                db.add(ReservoirSource(reservoir_id=rid, source_id=sid))
                n += 1
    return n


def panel_rows(panel: pd.DataFrame) -> pd.DataFrame:
    df = panel.copy()
    df["month"] = pd.to_datetime(df["date"])
    if "volume_valid" in df.columns:
        # Volume seulement dans le domaine de validité de la relation de Liebe (1-35 ha)
        df["volume_m3"] = df["volume_m3"].where(df["volume_valid"].astype(bool))
    keep = ["reservoir_id", "month", *[c for c in svc.PANEL_COLUMNS if c in df.columns]]
    return df[keep]


def run(dry_run: bool = False) -> None:
    reservoirs, regions, panel, bundle = load_inputs()
    logger.info("Fichiers : %d réservoirs, %d zones, panel %s, modèle %s (%s)",
                len(reservoirs), len(regions), panel.shape, bundle["version"], bundle["created"])
    missing = set(reservoirs) - set(regions)
    if missing:
        raise RuntimeError(f"Zones d'analyse manquantes pour {sorted(missing)}")
    if dry_run:
        logger.info("[dry-run] aucune écriture")
        return

    create_all()
    db = SessionLocal()
    try:
        n_res = upsert_reservoirs(db, reservoirs, regions, bundle)
        n_links = upsert_links(db, reservoirs)
        db.flush()
        obs = panel_rows(panel)
        n_obs = 0
        for start in range(0, len(obs), 2000):            # lots : limite de paramètres SQL
            n_obs += svc.upsert_observations(db, obs.iloc[start:start + 2000])
        db.commit()
        logger.info("Réservoirs : %d | liens source-réservoir : %d | observations : %d", n_res, n_links, n_obs)

        hist = svc.load_panel(db)
        fc = forecast(bundle, hist)
        version = f"{bundle['version']} ({bundle['created']})"
        n_fc = svc.upsert_forecasts(db, fc, version)
        n_src = svc.apply_forecasts_to_sources(db)
        db.commit()
        h1 = fc[fc["horizon"] == fc["horizon"].min()]
        logger.info("Prévisions émises fin %s : %d lignes | sources mises à jour : %d | statuts h=1 : %s",
                    fc["issue_month"].iloc[0], n_fc, n_src, h1["status"].value_counts().to_dict())
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Charge les résultats v3 du notebook en base")
    parser.add_argument("--dry-run", action="store_true")
    run(dry_run=parser.parse_args().dry_run)


if __name__ == "__main__":
    main()
