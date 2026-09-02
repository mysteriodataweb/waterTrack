"""
Synchronise la géométrie des sources d'eau avec les polygones réels des plans
d'eau OpenStreetMap (barrages, lacs, retenues, mares).

  1. Interroge Overpass API sur le bbox des sources => polygones water (ways).
  2. Fait correspondre chaque source au polygone qui la contient (le plus petit
     de préférence), sinon au plus proche à moins de 2 km.
  3. Met à jour water_sources.geometry + superficie_km2 (recalculée depuis le
     polygone), et régénère `frontend/public/water-polygons.geojson` utilisé
     par la carte pour dessiner les formes.

Usage :
  python -m scripts.sync_water_geometries          # base + GeoJSON
  python -m scripts.sync_water_geometries --no-db  # GeoJSON seul

Idempotent : les sources déjà en polygone sont re-travaillées si un meilleur
match est trouvé (contenant > plus proche) ; sinon elles restent inchangées.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("sync_water_geometries")

from sqlalchemy import text

from app.database import SessionLocal, engine, ensure_postgis

BACKEND_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_PUBLIC = BACKEND_ROOT.parent / "frontend" / "public"
GEOJSON_PATH = FRONTEND_PUBLIC / "water-polygons.geojson"

OVERLAP_RADIUS_M = 2000  # rayon de rattachement quand la source est hors polygone
USER_AGENT = "watertrack-geometry-sync/1.0"


def fetch_water_polygons(lat_min: float, lng_min: float, lat_max: float, lng_max: float):
    """Retourne [(osm_id, name, ring(lat,lng)), ...] depuis Overpass API."""
    query = f"""
    [out:json][timeout:180];
    (
      way["natural"="water"]({lat_min:.5f},{lng_min:.5f},{lat_max:.5f},{lng_max:.5f});
      way["water"="*"]({lat_min:.5f},{lng_min:.5f},{lat_max:.5f},{lng_max:.5f});
      way["waterway"="riverbank"]({lat_min:.5f},{lng_min:.5f},{lat_max:.5f},{lng_max:.5f});
      way["landuse"~"^(reservoir|basin|pond)$"]({lat_min:.5f},{lng_min:.5f},{lat_max:.5f},{lng_max:.5f});
      way["natural"="basin"]({lat_min:.5f},{lng_min:.5f},{lat_max:.5f},{lng_max:.5f});
    );
    out tags geom;
    """
    body = ("data=" + urllib.parse.quote(query)).encode("utf-8")
    url = "https://overpass-api.de/api/interpreter"

    def _call(u: str):
        req = urllib.request.Request(
            u, data=body, method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "*/*",
                "User-Agent": USER_AGENT,
            },
        )
        with urllib.request.urlopen(req, timeout=200) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        data = _call(url)
    except Exception as exc:
        logger.warning("overpass-api.de indisponible (%s), bascule sur kumi.systems", exc)
        data = _call("https://overpass.kumi.systems/api/interpreter")

    polygons = []
    for el in data.get("elements", []):
        geom = el.get("geometry")
        tags = el.get("tags") or {}
        if not geom or len(geom) < 3:
            continue
        name = tags.get("name") or tags.get("water") or tags.get("natural") \
            or tags.get("landuse") or "Plan d'eau"
        ring = [(g["lat"], g["lon"]) for g in geom]
        polygons.append((el["id"], name, ring))
    return polygons


def ensure_osm_table(db) -> None:
    db.execute(text("DROP TABLE IF EXISTS _osm_water"))
    db.execute(text(
        "CREATE TEMP TABLE _osm_water (osm_id BIGINT PRIMARY KEY, name TEXT, geom geometry)"
    ))


def load_polygons(db, polygons) -> int:
    rows = []
    for osm_id, name, ring in polygons:
        wkt = "POLYGON((" + ", ".join(f"{lng} {lat}" for lat, lng in ring) + "))"
        rows.append({"id": osm_id, "name": name, "wkt": wkt})
    db.execute(text("INSERT INTO _osm_water (osm_id, name, geom) "
                    "VALUES (:id, :name, ST_MakeValid(ST_GeomFromText(:wkt, 4326)))"),
               rows)
    return len(rows)


def match_for(db, source_id: int, lat: float, lng: float):
    """Polygone contenant la source (le plus petit), sinon le plus proche < 2 km."""
    point_sql = "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)"
    containing = db.execute(text(
        f"SELECT osm_id, name, geom, ST_Area(geom::geography) AS m2 FROM _osm_water "
        f"WHERE ST_Contains(geom, {point_sql}) ORDER BY ST_Area(geom) ASC LIMIT 1"
    ), {"lat": lat, "lng": lng}).mappings().first()
    if containing:
        return containing

    nearest = db.execute(text(
        f"SELECT osm_id, name, geom, ST_Area(geom::geography) AS m2, "
        f"ST_Distance(geom::geography, {point_sql}::geography) AS dist FROM _osm_water "
        f"ORDER BY geom <-> {point_sql} ASC LIMIT 1"
    ), {"lat": lat, "lng": lng}).mappings().first()
    if nearest and nearest["dist"] <= OVERLAP_RADIUS_M:
        return nearest
    return None


def first_ring_coords(geom_geojson: dict) -> list[list[float]]:
    """Premier anneau en [[lng, lat], ...] (GeoJSON)."""
    if geom_geojson.get("type") == "Polygon":
        return geom_geojson["coordinates"][0]
    # MultiPolygon : plus grande surface
    polys = geom_geojson.get("coordinates") or []
    if polys:
        return max(polys, key=lambda p: abs(ring_area(p[0])))[0]
    return []


def ring_area(ring: list) -> float:
    """Aire planaire (stabilité pour le choix de boucle)."""
    return sum(_signed(ring, i) for i in range(len(ring) - 1))


def _signed(ring: list, i: int) -> float:
    x1, y1 = ring[i]; x2, y2 = ring[i + 1]
    return x1 * y2 - x2 * y1


def run(update_db: bool = True) -> None:
    ensure_postgis()
    db = SessionLocal()
    try:
        bbox = db.execute(text(
            "SELECT min(latitude), min(longitude), max(latitude), max(longitude) "
            "FROM water_sources"
        )).one()
        lat_min, lng_min, lat_max, lng_max = bbox
        # Padding léger pour ne pas couper les plans d'eau en bord de zone.
        lat_min -= 0.02; lng_min -= 0.02; lat_max += 0.02; lng_max += 0.02

        logger.info("Récupération des polygones OSM (%s)...", f"{lat_min:.2f},{lng_min:.2f},{lat_max:.2f},{lng_max:.2f}")
        t0 = time.time()
        polygons = fetch_water_polygons(lat_min, lng_min, lat_max, lng_max)
        logger.info("  %d polygones en %.1fs", len(polygons), time.time() - t0)

        if not polygons:
            logger.error("Aucun polygone récupéré, abandon.")
            return

        ensure_osm_table(db)
        loaded = load_polygons(db, polygons)
        logger.info("  %d polygones chargés en mémoire", loaded)

        sources = db.execute(text(
            "SELECT id, latitude, longitude FROM water_sources ORDER BY id"
        )).all()

        updated = 0
        matched = 0
        features = []
        for source in sources:
            sid, lat, lng = source.id, source.latitude, source.longitude
            match = match_for(db, sid, lat, lng)
            core = {
                "source_id": sid,
                "name": match["name"] if match else None,
                "osm_id": match["osm_id"] if match else None,
            }
            if not match:
                features.append({"type": "Feature", "properties": core, "geometry": None})
                continue

            matched += 1
            geom_geojson = json.loads(db.execute(text(
                "SELECT ST_AsGeoJSON(geom) FROM _osm_water WHERE osm_id = :oid"
            ), {"oid": match["osm_id"]}).scalar())
            ring = first_ring_coords(geom_geojson)
            if len(ring) < 4:
                continue
            km2 = round(match["m2"] / 1_000_000.0, 3)
            features.append({
                "type": "Feature",
                "properties": {**core, "superficie_km2": km2},
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            })

            if update_db:
                res = db.execute(text(
                    "UPDATE water_sources SET geometry = ST_MakeValid(:geom), "
                    "superficie_km2 = :km2, date_analyse = COALESCE(date_analyse, CURRENT_DATE) "
                    "WHERE id = :sid RETURNING id"
                ), {"geom": geom_geojson, "km2": km2, "sid": sid}).scalar()
                if res:
                    updated += 1
                if updated % 20 == 0:
                    db.commit()

        if update_db:
            db.commit()
            logger.info("DB mise à jour : %d/%d sources en polygone.", updated, matched)

        if not GEOJSON_PATH.parent.exists():
            GEOJSON_PATH.parent.mkdir(parents=True)
        GEOJSON_PATH.write_text(json.dumps(
            {"type": "FeatureCollection", "features": features}, ensure_ascii=False
        ), encoding="utf-8")
        logger.info("GeoJSON écrit : %s (%d formes, %d sans match)",
                    GEOJSON_PATH, sum(1 for f in features if f["geometry"]),
                    sum(1 for f in features if not f["geometry"]))
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-db", action="store_true", help="Ne pas toucher à la base")
    args = parser.parse_args()
    run(update_db=not args.no_db)