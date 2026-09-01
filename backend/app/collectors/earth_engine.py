from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path
from typing import Optional

import ee

from ..config import settings

logger = logging.getLogger(__name__)

# Variables d'environnement proxy à neutraliser si elles pointent vers localhost:9
_PREPROXY_VARS = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
    "http_proxy", "https_proxy", "all_proxy",
    "GIT_HTTP_PROXY", "GIT_HTTPS_PROXY",
)


def _clear_broken_proxy() -> None:
    for var in _PREPROXY_VARS:
        value = os.environ.get(var)
        if value and ("127.0.0.1:9" in value or "localhost:9" in value):
            os.environ.pop(var, None)


class EarthEngineClient:
    """Client Google Earth Engine : collecte satellite (Sentinel-2) → NDWI/NDVI."""

    def __init__(self) -> None:
        self._initialized = False
        self._zone = None

    # ------------------------------------------------------------------ #
    def initialize(self) -> None:
        if self._initialized:
            return
        _clear_broken_proxy()
        try:
            ee.Initialize(project=settings.gee_project)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Impossible d'initialiser Google Earth Engine. "
                "Vérifie la connectivité réseau et les credentials "
                "(`earthengine authenticate`)."
            ) from exc
        self._initialized = True

    @property
    def zone(self) -> ee.Geometry:
        lat, lng = settings.watch_center
        return ee.Geometry.Point([lng, lat]).buffer(settings.watch_radius_m)

    # ------------------------------------------------------------------ #
    def detect_water_sources(self, ndwi_threshold: float = 0.2) -> list[dict]:
        """Redétecte les zones d'eau dans la zone de surveillance via satellite.

        Prend une image Sentinel-2 récente (période des pluies la plus récente),
        calcule le NDWI et vectorise les pixels d'eau en polygones.

        La détection se fait en tuiles (tileScale) et à résolution moyenne pour
        rester sous la limite de mémoire gratuite d'Earth Engine (qui peut
        exploser sur une grande zone à scale=20 avec reduceToVectors).
        """
        self.initialize()

        image = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(self.zone)
            .filterDate("2024-01-01", date.today().isoformat())
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
            .median()
        )

        # NDWI = (Green - NIR) / (Green + NIR)  → B3 (vert), B8 (NIR)
        ndwi = image.normalizedDifference(["B3", "B8"]).rename("NDWI")
        mask = ndwi.gt(ndwi_threshold)

        vectors = mask.updateMask(mask).reduceToVectors(
            geometry=self.zone,
            scale=100,          # résolution de la détection (silhouettes des plans d'eau)
            maxPixels=1e8,
            bestEffort=True,
            geometryType="polygon",
            eightConnected=False,
            tileScale=8,        # découpe le calcul en tuiles → évite la surcharge mémoire
        )

        feats = vectors.getInfo().get("features", [])
        sources = []
        for feat in feats:
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates")
            if not coords:
                continue
            # Ignorer les micro-zones (bruit) : surface minimale ~ 5 000 m².
            area_km2 = _estimate_area_km2(geom)
            if area_km2 < 0.005:
                continue
            centroid = _centroid(coords)
            if centroid is None:
                continue
            lon, lat = centroid
            sources.append({
                "longitude": lon,
                "latitude": lat,
                "geometry": geom,
                "area_km2": area_km2,
            })
        return sources

    # ------------------------------------------------------------------ #
    def collect_period(self, debut: str, fin: str, label: str, saison: str,
                       sources: list[dict]) -> list[dict]:
        """Calcule le NDWI/NDVI moyen de chaque source pour une période donnée."""
        self.initialize()

        image = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(self.zone)
            .filterDate(debut, fin)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
            .median()
        )

        ndwi = image.normalizedDifference(["B3", "B8"]).rename("NDWI")
        ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")

        # Points des sources
        pts = ee.FeatureCollection([
            ee.Feature(ee.Geometry.Point([s["longitude"], s["latitude"]]), {"idx": i})
            for i, s in enumerate(sources)
        ])

        stats = ndwi.addBands(ndvi).reduceRegions(
            collection=pts,
            reducer=ee.Reducer.mean(),
            scale=20,
        )

        outcomes = stats.getInfo().get("features", [])
        by_idx = {int(f["properties"].get("idx")): f["properties"] for f in outcomes}

        rows = []
        for i, s in enumerate(sources):
            props = by_idx.get(i, {})
            ndwi_val = props.get("NDWI")
            ndvi_val = props.get("NDVI")
            if ndwi_val is None:
                continue
            rows.append({
                "periode": label,
                "saison": saison,
                "debut": debut,
                "fin": fin,
                "ndwi": float(ndwi_val),
                "ndvi": float(ndvi_val) if ndvi_val is not None else None,
                "longitude": s["longitude"],
                "latitude": s["latitude"],
                "geometry": s.get("geometry"),
                "area_km2": s.get("area_km2"),
            })
        return rows


# --------------------------------------------------------------------- #
# Helpers géométriques
# --------------------------------------------------------------------- #
def _collect_pairs(value) -> list[tuple[float, float]]:
    if not isinstance(value, list):
        return []
    if len(value) >= 2 and isinstance(value[0], (int, float)) and isinstance(value[1], (int, float)):
        return [(float(value[0]), float(value[1]))]
    out = []
    for item in value:
        out.extend(_collect_pairs(item))
    return out


def _norm_geometry(geometry):
    """Normalise une géométrie EE : dict {type, coordinates} ou liste brute."""
    if isinstance(geometry, dict):
        return geometry
    if isinstance(geometry, list):
        return {"type": "Geometry", "coordinates": geometry}
    return {}


def _centroid(geometry) -> Optional[tuple[float, float]]:
    norm = _norm_geometry(geometry)
    pairs = _collect_pairs(norm.get("coordinates"))
    if not pairs:
        return None
    lon = sum(p[0] for p in pairs) / len(pairs)
    lat = sum(p[1] for p in pairs) / len(pairs)
    return lon, lat


def _estimate_area_km2(geometry) -> float:
    norm = _norm_geometry(geometry)
    if norm.get("type") != "Polygon":
        return 0.0
    ring = norm.get("coordinates", [])
    if not ring:
        return 0.0
    points = _collect_pairs(ring[0])
    if len(points) < 4:
        return 0.0
    mean_lat = sum(p[1] for p in points) / len(points)
    km_per_lng = 111.32 * max(0.0, _cosd(mean_lat))
    proj = [(p[0] * km_per_lng, p[1] * 110.57) for p in points]
    area = 0.0
    for i in range(len(proj)):
        x1, y1 = proj[i]
        x2, y2 = proj[(i + 1) % len(proj)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _cosd(deg: float) -> float:
    import math
    return math.cos(math.radians(deg))
