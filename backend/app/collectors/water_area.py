"""
Collecte mensuelle v3 : surface en eau de chaque réservoir + forçages climatiques.

Version opérationnelle de la chaîne d'extraction du notebook
(`notebooks/WaterTracker_pipeline.ipynb`, §3-4). Les paramètres ci-dessous
DOIVENT rester identiques à ceux du notebook, sinon les nouvelles mesures ne
seraient pas comparables à celles sur lesquelles le modèle a été entraîné.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor

import ee
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---- Paramètres de la chaîne (identiques au notebook) ---- #
SCALE_M = 10                      # résolution de mesure (m)
CS_THRESHOLD = 0.60               # Cloud Score+ (cs_cdf) minimal d'un pixel clair
VALID_MIN = 0.90                  # part de pixels optiques valides pour une observation S2 fiable
MAX_FILL = 1.5                    # borne haute du taux de remplissage
LIEBE_K, LIEBE_EXP = 0.00857, 1.4367   # V = k · A^exp (Liebe et al., 2005), m³ / m²
LIEBE_RANGE_HA = (1.0, 35.0)
REQUEST_RETRIES = 4

S2_COL = "COPERNICUS/S2_SR_HARMONIZED"
CS_COL = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
S1_COL = "COPERNICUS/S1_GRD"
CHIRPS_COL = "UCSB-CHG/CHIRPS/DAILY"
ERA5_COL = "ECMWF/ERA5_LAND/MONTHLY_AGGR"
ERA5_BANDS = {
    "temperature_2m": "t2m_k",
    "potential_evaporation_sum": "pet_m",
    "total_evaporation_sum": "aet_m",
    "volumetric_soil_water_layer_1": "soil_moist",
}


# --------------------------------------------------------------------------- #
# Outils Earth Engine
# --------------------------------------------------------------------------- #
def ee_to_df(fc: ee.FeatureCollection) -> pd.DataFrame:
    """FeatureCollection -> DataFrame, avec reprises (quota, délai, coupure réseau)."""
    for attempt in range(REQUEST_RETRIES):
        try:
            df = ee.data.computeFeatures({"expression": fc, "fileFormat": "PANDAS_DATAFRAME"})
            return df.drop(columns=["geo"], errors="ignore")
        except Exception as exc:  # noqa: BLE001
            if attempt == REQUEST_RETRIES - 1:
                raise
            wait = 5 * 2 ** attempt
            logger.warning("GEE : %s -> nouvelle tentative dans %ss", exc, wait)
            time.sleep(wait)
    raise RuntimeError("inaccessible")


def last_available_month() -> str:
    """Dernier mois disponible à la fois dans ERA5-Land et CHIRPS (publiés avec retard)."""
    def last(col: str) -> str:
        img = ee.ImageCollection(col).sort("system:time_start", False).first()
        return ee.Date(img.get("system:time_start")).format("YYYY-MM").getInfo()

    last_complete = (pd.Timestamp.today().to_period("M") - 1).strftime("%Y-%m")
    return min(last(ERA5_COL), last(CHIRPS_COL), last_complete)


def regions_collection(regions: dict[str, dict]) -> tuple[ee.FeatureCollection, ee.Geometry]:
    """{reservoir_id: GeoJSON} -> (FeatureCollection, rectangle englobant)."""
    fc = ee.FeatureCollection([
        ee.Feature(ee.Geometry(geom), {"reservoir_id": rid}) for rid, geom in regions.items()
    ])
    coords = np.array([
        pt for geom in regions.values() for pt in _iter_coords(geom["coordinates"])
    ])
    bbox = ee.Geometry.Rectangle([coords[:, 0].min(), coords[:, 1].min(), coords[:, 0].max(), coords[:, 1].max()])
    return fc, bbox


def _iter_coords(c):
    if isinstance(c[0], (int, float)):
        yield c[:2]
    else:
        for item in c:
            yield from _iter_coords(item)


# --------------------------------------------------------------------------- #
# Mesures mensuelles
# --------------------------------------------------------------------------- #
def _mask_and_sharpen(im: ee.Image) -> ee.Image:
    im = im.updateMask(im.select("cs_cdf").gte(CS_THRESHOLD))
    # Affinage de B11 (20 m) sur la grille 10 m avant le MNDWI (Du et al., 2016)
    return im.addBands(im.select("B11").resample("bilinear"), overwrite=True)


def s2_month(month: str, fc: ee.FeatureCollection, bbox: ee.Geometry) -> pd.DataFrame:
    start = ee.Date.parse("YYYY-MM", month)
    col = (
        ee.ImageCollection(S2_COL).filterBounds(bbox).filterDate(start, start.advance(1, "month"))
        .linkCollection(ee.ImageCollection(CS_COL), ["cs_cdf"]).map(_mask_and_sharpen)
    )
    mndwi = col.median().normalizedDifference(["B3", "B11"])
    pa = ee.Image.pixelArea()
    img = ee.Image.cat([
        mndwi.gt(0).unmask(0).multiply(pa).rename("water_m2"),
        mndwi.mask().unmask(0).multiply(pa).rename("valid_m2"),
        pa.rename("region_m2"),
    ])
    out = img.reduceRegions(collection=fc, reducer=ee.Reducer.sum(), scale=SCALE_M, tileScale=4)
    return ee_to_df(out.map(lambda f: f.setGeometry(None)))


def s1_month(month: str, fc: ee.FeatureCollection, bbox: ee.Geometry, threshold_db: float) -> pd.DataFrame:
    start = ee.Date.parse("YYYY-MM", month)
    vv = (
        ee.ImageCollection(S1_COL).filterBounds(bbox).filterDate(start, start.advance(1, "month"))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .select("VV").median()
    )
    img = vv.lt(threshold_db).unmask(0).multiply(ee.Image.pixelArea())
    # Image à une seule bande : GEE nommerait la sortie « sum » ; on la nomme explicitement.
    reducer = ee.Reducer.sum().setOutputs(["s1_water_m2"])
    out = img.reduceRegions(collection=fc, reducer=reducer, scale=SCALE_M, tileScale=4)
    return ee_to_df(out.map(lambda f: f.setGeometry(None)))


def climate_month(month: str, hybas_ids: list[int]) -> pd.DataFrame:
    start = ee.Date.parse("YYYY-MM", month)
    end = start.advance(1, "month")
    basins = ee.FeatureCollection("WWF/HydroSHEDS/v1/Basins/hybas_10").filter(ee.Filter.inList("HYBAS_ID", hybas_ids))
    basins = basins.map(lambda f: ee.Feature(f.geometry(), {"hybas_id": f.get("HYBAS_ID")}))
    precip = ee.ImageCollection(CHIRPS_COL).filterDate(start, end).sum().rename("precip_mm")
    era5 = ee.Image(ee.ImageCollection(ERA5_COL).filterDate(start, end).first()).select(
        list(ERA5_BANDS), list(ERA5_BANDS.values())
    )
    out = precip.addBands(era5).reduceRegions(collection=basins, reducer=ee.Reducer.mean(), scale=5000)
    df = ee_to_df(out.map(lambda f: f.setGeometry(None)))
    df["t2m_c"] = df.pop("t2m_k") - 273.15
    df["pet_mm"] = -df.pop("pet_m") * 1000
    df["aet_mm"] = -df.pop("aet_m") * 1000
    df["hybas_id"] = df["hybas_id"].astype("int64")
    return df


# --------------------------------------------------------------------------- #
# Fusion S2 / S1 -> taux de remplissage
# --------------------------------------------------------------------------- #
def area_to_volume_m3(area_ha):
    return LIEBE_K * (np.asarray(area_ha, dtype=float) * 1e4) ** LIEBE_EXP


def s1_threshold_from_column(column: str) -> float:
    """'s1_water_20_ha' -> -20.0 dB (nom de colonne retenu par le notebook)."""
    return -float(column.split("_")[2])


def fuse(s2: pd.DataFrame, s1: pd.DataFrame, s1_mapping: pd.DataFrame, a_ref: pd.Series) -> pd.DataFrame:
    """Règles de fusion du notebook (§4.4) : S2 fiable, sinon S1 recalibré, sinon manquant."""
    df = s2.merge(s1[["reservoir_id", "s1_water_m2"]], on="reservoir_id", how="left")
    df["valid_frac"] = df["valid_m2"] / df["region_m2"]
    df["water_ha"] = df["water_m2"] / 1e4
    m = df[["reservoir_id"]].join(s1_mapping[["a", "b", "usable"]], on="reservoir_id")
    s1_est = (m["a"] + m["b"] * df["s1_water_m2"] / 1e4).clip(lower=0)
    s1_est = s1_est.where(m["usable"].fillna(False).astype(bool))
    reliable = df["valid_frac"] >= VALID_MIN
    df["area_ha"] = np.where(reliable, df["water_ha"], s1_est)
    df["area_source"] = np.select([reliable, s1_est.notna()], ["S2", "S1"], default="manquant")
    df["a_ref_ha"] = df["reservoir_id"].map(a_ref)
    df["fill"] = (df["area_ha"] / df["a_ref_ha"]).clip(upper=MAX_FILL)
    in_range = df["a_ref_ha"].between(*LIEBE_RANGE_HA)
    df["volume_m3"] = np.where(in_range, area_to_volume_m3(df["area_ha"]), np.nan)
    return df


def collect_month(month: str, regions: dict[str, dict], hybas_by_reservoir: dict[str, int], bundle: dict) -> pd.DataFrame:
    """Une ligne par réservoir : surface, taux de remplissage, provenance, forçages climatiques."""
    fc, bbox = regions_collection(regions)
    threshold = s1_threshold_from_column(bundle["s1_column"])
    hybas_ids = sorted({int(h) for h in hybas_by_reservoir.values() if h is not None})
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_s2 = pool.submit(s2_month, month, fc, bbox)
        f_s1 = pool.submit(s1_month, month, fc, bbox, threshold)
        f_cl = pool.submit(climate_month, month, hybas_ids)
        s2, s1, clim = f_s2.result(), f_s1.result(), f_cl.result()

    df = fuse(s2, s1, bundle["s1_mapping"], bundle["a_ref_ha"])
    df["hybas_id"] = df["reservoir_id"].map(hybas_by_reservoir)
    df = df.merge(clim, on="hybas_id", how="left")
    df["month"] = pd.Period(month, "M").to_timestamp()
    return df
