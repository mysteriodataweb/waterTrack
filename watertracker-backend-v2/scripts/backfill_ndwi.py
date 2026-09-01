"""
Backfill initial — construit la base de données à partir de ZÉRO en utilisant
les VRAIES données satellite (Google Earth Engine).

Étapes :
  1. Redétecte les sources d'eau dans la zone de surveillance (Sentinel-2).
  2. Remplit l'historique NDWI/NDVI période par période depuis 2020.
  3. Persiste dans PostgreSQL/PostGIS (water_sources + ndwi_observations).

Usage :
  python -m scripts.backfill_ndwi [--dry-run]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Permet d'importer le package `app` depuis la racine du projet.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("backfill")

from sqlalchemy import select
from geoalchemy2 import WKTElement  # noqa: F401

from app.collectors.earth_engine import EarthEngineClient
from app.database import SessionLocal, create_all, ensure_postgis
from app.models import WaterSource, NdwiObservation

# Périodes semestrielles depuis 2020 (début de l'historique satellite).
PERIODES = [
    {"label": "2020-S1", "debut": "2020-01-01", "fin": "2020-06-30", "saison": "seche"},
    {"label": "2020-S2", "debut": "2020-07-01", "fin": "2020-12-31", "saison": "pluies"},
    {"label": "2021-S1", "debut": "2021-01-01", "fin": "2021-06-30", "saison": "seche"},
    {"label": "2021-S2", "debut": "2021-07-01", "fin": "2021-12-31", "saison": "pluies"},
    {"label": "2022-S1", "debut": "2022-01-01", "fin": "2022-06-30", "saison": "seche"},
    {"label": "2022-S2", "debut": "2022-07-01", "fin": "2022-12-31", "saison": "pluies"},
    {"label": "2023-S1", "debut": "2023-01-01", "fin": "2023-06-30", "saison": "seche"},
    {"label": "2023-S2", "debut": "2023-07-01", "fin": "2023-12-31", "saison": "pluies"},
    {"label": "2024-S1", "debut": "2024-01-01", "fin": "2024-06-30", "saison": "seche"},
    {"label": "2024-S2", "debut": "2024-07-01", "fin": "2024-12-31", "saison": "pluies"},
]


def gps_key(lon: float, lat: float) -> str:
    return f"{lon:.6f}_{lat:.6f}"


def run(dry_run: bool = False) -> None:
    create_all()

    client = EarthEngineClient()
    logger.info("Détection des sources d'eau via satellite...")
    detected = client.detect_water_sources()
    logger.info("Sources détectées : %d", len(detected))

    if not detected:
        logger.error("Aucune source détectée. Vérifie la zone / le signal satellite.")
        return

    all_obs: list[dict] = []
    for period in PERIODES:
        logger.info("Collecte %s (%s → %s)...", period["label"], period["debut"], period["fin"])
        rows = client.collect_period(
            debut=period["debut"], fin=period["fin"],
            label=period["label"], saison=period["saison"],
            sources=detected,
        )
        all_obs.extend(rows)
        logger.info("  → %d mesures", len(rows))

    if dry_run:
        logger.info("[dry-run] Aucune écriture en base.")
        logger.info("Total mesures : %d | Sources : %d", len(all_obs), len(detected))
        return

    db = SessionLocal()
    try:
        # 1. Insère les sources (clé GPS unique)
        source_map: dict[str, WaterSource] = {}
        for d in detected:
            key = gps_key(d["longitude"], d["latitude"])
            existing = db.execute(
                select(WaterSource).where(WaterSource.gps_key == key)
            ).scalar_one_or_none()
            if existing:
                source_map[key] = existing
                continue
            try:
                from scripts.backfill_zones import reverse_geocode_zone
                zone_detail = reverse_geocode_zone(d["latitude"], d["longitude"])
            except Exception:  # noqa: BLE001
                zone_detail = None
            source = WaterSource(
                gps_key=key,
                longitude=d["longitude"],
                latitude=d["latitude"],
                zone="Ouagadougou",
                zone_detail=zone_detail,
                superficie_km2=d.get("area_km2"),
                geometry=WKTElement(
                    f"POINT({d['longitude']} {d['latitude']})", srid=4326
                ),
            )
            db.add(source)
            db.flush()
            source_map[key] = source

        # 2. Insère les observations NDWI/NDVI (upsert par source+periode)
        obs_keys = db.execute(
            select(NdwiObservation.source_id, NdwiObservation.periode)
        ).all()
        existing_keys = {(o.source_id, o.periode) for o in obs_keys}

        inserted = 0
        for o in all_obs:
            key = gps_key(o["longitude"], o["latitude"])
            source = source_map.get(key)
            if source is None:
                continue
            if (source.id, o["periode"]) in existing_keys:
                continue
            observation = NdwiObservation(
                source_id=source.id,
                periode=o["periode"],
                observation_date=_period_date(o["periode"]),
                saison=o["saison"],
                ndwi=o["ndwi"],
                ndvi=o["ndvi"],
                satellite="sentinel-2",
            )
            db.add(observation)
            inserted += 1

        # 3. Recalcule ndwi_moyen de chaque source = moyenne des observations.
        from sqlalchemy import func
        for s in source_map.values():
            avg = db.execute(
                select(func.avg(NdwiObservation.ndwi)).where(
                    NdwiObservation.source_id == s.id
                )
            ).scalar()
            if avg is not None:
                s.ndwi_moyen = float(avg)
            from datetime import date
            s.date_analyse = date.today()

        db.commit()
        logger.info("Terminé : %d sources, %d nouvelles observations insérées.",
                    len(source_map), inserted)
    finally:
        db.close()


def _period_date(periode: str) -> "object":
    from datetime import date
    annee = int(periode.split("-")[0])
    sem = 1 if periode.endswith("S1") else 2
    return date(annee, 1 if sem == 1 else 7, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill NDWI depuis satellites")
    parser.add_argument("--dry-run", action="store_true", help="Ne rien écrire en base")
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
