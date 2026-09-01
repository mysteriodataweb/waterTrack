"""
Backfill de la zone précise (province/commune) pour chaque source d'eau.

Utilise le géocodage inverse OpenRouteService (~1 appel / source) pour dériver
une zone stable ("kadiogo", "oubritenga", "bazega"...). Si le géocodage échoue,
retombe sur "Ouagadougou".

Usage :
  python -m scripts.backfill_zones
"""
from __future__ import annotations

import json
import logging
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("backfill_zones")

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal, engine, ensure_postgis
from app.models import WaterSource


def _slugify(value: str) -> str:
    """'Bazèga' -> 'bazega', 'Kadiogo' -> 'kadiogo'."""
    value = value.lower()
    value = value.replace("é", "e").replace("è", "e").replace("ê", "e").replace("ë", "e")
    value = value.replace("à", "a").replace("â", "a").replace("ô", "o")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "ouagadougou"


def reverse_geocode_zone(lat: float, lng: float) -> str:
    """Retourne la province (comté) en minuscules, sinon 'ouagadougou'."""
    if not settings.openroute_api_key:
        return "ouagadougou"
    query = urllib.parse.urlencode({
        "api_key": settings.openroute_api_key,
        "point.lon": lng, "point.lat": lat, "size": 1, "lang": "fr",
    })
    req = urllib.request.Request(
        f"https://api.openrouteservice.org/geocode/reverse?{query}",
        method="GET",
        headers={"Authorization": settings.openroute_api_key, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError):
        return "ouagadougou"

    features = data.get("features") or []
    if not features:
        return "ouagadougou"
    props = features[0].get("properties") or {}
    county = props.get("county")
    if county:
        return _slugify(county)
    locality = props.get("locality")
    if locality:
        return _slugify(locality)
    label = props.get("label") or ""
    if label and "," in label:
        return _slugify(label.split(",")[0])
    return "ouagadougou"


def ensure_zone_detail_column() -> bool:
    """Ajoute la colonne zone_detail si elle manque. Retourne True si ajoutée."""
    with engine.begin() as conn:
        exists = conn.execute(
            __import__("sqlalchemy").text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_name='water_sources' AND column_name='zone_detail')"
            )
        ).scalar()
        if not exists:
            conn.execute(__import__("sqlalchemy").text(
                "ALTER TABLE water_sources ADD COLUMN zone_detail VARCHAR DEFAULT 'Ouagadougou'"
            ))
            return True
    return False


def run() -> None:
    ensure_postgis()
    added = ensure_zone_detail_column()
    if added:
        logger.info("Colonne zone_detail ajoutée.")

    db = SessionLocal()
    try:
        sources = db.execute(select(WaterSource)).scalars().all()
        logger.info("Sources à traiter : %d", len(sources))
        updated = 0
        for i, source in enumerate(sources):
            zone = reverse_geocode_zone(source.latitude, source.longitude)
            if zone and zone != (source.zone_detail or ""):
                source.zone_detail = zone
                updated += 1
            # Rate-limit léger : 65 appels avec ~0.35s = ~23s total.
            if (i + 1) % 10 == 0:
                logger.info("  %d/%d traitées...", i + 1, len(sources))
                time.sleep(1)
        db.commit()
        logger.info("Terminé : %d sources mis à jour (zone_detail).", updated)

        # Récapitulatif par zone
        counts: dict[str, int] = {}
        for s in db.execute(select(WaterSource)).scalars().all():
            z = s.zone_detail or "ouagadougou"
            counts[z] = counts.get(z, 0) + 1
        for z, c in sorted(counts.items()):
            logger.info("  %s : %d source(s)", z, c)
    finally:
        db.close()


if __name__ == "__main__":
    run()