"""
Restaure l'inventaire des sources dans une base vide (changement d'hébergeur,
base perdue), puis recollecte leur historique NDWI. Idempotent.

  1. `water_sources` : relu depuis `data/water_sources.json`, une sauvegarde de
     la réponse de `GET /api/water-sources`. Les identifiants sont conservés
     (les réservoirs v3 y font référence), ainsi que les contours.
  2. `ndwi_observations` : recollecté depuis Sentinel-2 (Earth Engine) aux mêmes
     coordonnées et sur les mêmes semestres que le backfill d'origine.

À faire suivre de `python -m scripts.load_v3` (réservoirs, surfaces, prévisions).

Usage :
  python -m scripts.restore_sources              # sources + historique NDWI
  python -m scripts.restore_sources --skip-ndwi  # sources seulement (sans Earth Engine)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("restore_sources")

from sqlalchemy import select, text

from app.database import SessionLocal, create_all
from app.models import NdwiObservation, WaterSource
from scripts.backfill_ndwi import PERIODES, _period_date, gps_key

BACKUP = Path(__file__).resolve().parent.parent / "data" / "water_sources.json"


def restore_sources(db) -> int:
    items = json.loads(BACKUP.read_text(encoding="utf-8"))["items"]
    existing = set(db.execute(select(WaterSource.id)).scalars())
    stmt = text("""
        INSERT INTO water_sources (id, geometry, gps_key, longitude, latitude, zone, zone_detail,
                                   superficie_km2, ndwi_moyen, risk_score, status, date_analyse, created_at)
        VALUES (:id, ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326), :gps_key, :longitude, :latitude, :zone, :zone_detail,
                :superficie_km2, :ndwi_moyen, :risk_score, :status, :date_analyse, now())
    """)
    n = 0
    for it in items:
        if it["id"] in existing:
            continue
        # Sans contour sauvegardé, on retombe sur le point de la source
        geom = it.get("geometry") or {"type": "Point", "coordinates": [it["longitude"], it["latitude"]]}
        db.execute(stmt, {
            "id": it["id"],
            "geom": json.dumps(geom),
            "gps_key": gps_key(it["longitude"], it["latitude"]),
            "longitude": it["longitude"],
            "latitude": it["latitude"],
            "zone": it.get("zone") or "Ouagadougou",
            "zone_detail": it.get("zone_detail"),
            "superficie_km2": it.get("superficie_km2"),
            "ndwi_moyen": it.get("ndwi_moyen"),
            "risk_score": it.get("risk_score") or 0.0,
            "status": it.get("status") or "actif",
            "date_analyse": date.fromisoformat(it["date_analyse"]) if it.get("date_analyse") else None,
        })
        n += 1
    # Les identifiants ont été insérés tels quels : la séquence doit repartir après le dernier
    db.execute(text(
        "SELECT setval(pg_get_serial_sequence('water_sources', 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) "
        "FROM water_sources"
    ))
    return n


def restore_ndwi(db) -> int:
    from app.collectors.earth_engine import EarthEngineClient

    # Valeurs simples, puis fin de transaction : une collecte dure plusieurs minutes et
    # l'hébergeur coupe les connexions inactives. Rien ne doit rester ouvert pendant l'attente.
    sources = db.execute(
        select(WaterSource.id, WaterSource.longitude, WaterSource.latitude).order_by(WaterSource.id)
    ).tuples().all()
    done = set(db.execute(select(NdwiObservation.source_id, NdwiObservation.periode)).tuples())
    db.commit()
    payload = [{"longitude": lon, "latitude": lat} for _, lon, lat in sources]
    by_coords = {(lon, lat): source_id for source_id, lon, lat in sources}
    client = EarthEngineClient()
    inserted = 0
    for period in PERIODES:
        if all((source_id, period["label"]) in done for source_id, _, _ in sources):
            continue
        rows = client.collect_period(period["debut"], period["fin"], period["label"], period["saison"], payload)
        n = 0
        for r in rows:
            source_id = by_coords[(r["longitude"], r["latitude"])]
            if (source_id, period["label"]) in done:
                continue
            db.add(NdwiObservation(
                source_id=source_id,
                periode=period["label"],
                observation_date=_period_date(period["label"]),
                saison=period["saison"],
                ndwi=r["ndwi"],
                ndvi=r["ndvi"],
                satellite="sentinel-2",
            ))
            n += 1
        db.commit()  # par semestre : une coupure réseau ne fait pas tout reprendre
        inserted += n
        logger.info("Collecte %s : %d mesures", period["label"], n)
    return inserted


def run(skip_ndwi: bool = False) -> None:
    if not BACKUP.exists():
        raise FileNotFoundError(f"{BACKUP} manquant : sauvegarde de GET /api/water-sources")
    create_all()
    db = SessionLocal()
    try:
        n_src = restore_sources(db)
        db.commit()
        logger.info("Sources restaurées : %d", n_src)
        if not skip_ndwi:
            logger.info("Observations NDWI recollectées : %d", restore_ndwi(db))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Restaure les sources et leur historique NDWI")
    parser.add_argument("--skip-ndwi", action="store_true", help="ne pas recollecter l'historique NDWI")
    run(skip_ndwi=parser.parse_args().skip_ndwi)


if __name__ == "__main__":
    main()
