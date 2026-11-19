"""
Détection de l'eau pixel par pixel : imagettes Sentinel-2 et étiquettes d'entraînement.

Pourquoi un modèle par pixel : la mesure actuelle (`app/collectors/water_area.py`)
classe chaque pixel seul, avec un seuil sur un indice (MNDWI > 0). Elle se trompe
là où l'indice est ambigu : bords, eau turbide ou peu profonde, végétation
aquatique. Un réseau qui voit le voisinage et toutes les bandes peut trancher.

Ce module ne dépend pas de PyTorch. Il fait trois choses :
  1. choisir où et quand prélever des imagettes de 128 × 128 pixels à 10 m
     (autour des retenues suivies, plus des lieux sans retenue) ;
  2. les télécharger depuis Earth Engine : composite mensuel Sentinel-2 préparé
     comme dans la chaîne opérationnelle, plus deux sources indépendantes
     (probabilité d'eau Dynamic World, rétrodiffusion radar Sentinel-1) ;
  3. construire des étiquettes sans saisie manuelle.

Étiquettes (« consensus ») : un pixel est « eau » si l'indice MNDWI ET Dynamic
World le disent nettement, « pas eau » si les deux disent nettement non. Tous les
autres pixels sont IGNORÉS à l'entraînement : ce sont justement les cas ambigus
sur lesquels le réseau doit généraliser, et que l'on évalue ensuite avec le radar.

Limite : ces étiquettes ne sont pas une vérité de terrain. Elles sont fiables là
où elles existent, mais absentes là où la question est difficile.

Usage :
  python -m ml.unet_data --out data/unet            # extraction complète
  python -m ml.unet_data --out data/unet --limit 20 # essai rapide
"""
from __future__ import annotations

import argparse
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger("unet_data")

# ---- Géométrie des imagettes ---- #
CHIP = 128                        # côté en pixels
SCALE_M = 10                      # résolution (m), grille Sentinel-2
CRS = "EPSG:32630"                # UTM 30N : toute la zone d'étude
CHIP_M = CHIP * SCALE_M
BLOCK_M = 10_000                  # blocs spatiaux pour séparer entraînement / validation / test

# ---- Sources Earth Engine (mêmes réglages que la chaîne opérationnelle) ---- #
S2_COL = "COPERNICUS/S2_SR_HARMONIZED"
CS_COL = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
DW_COL = "GOOGLE/DYNAMICWORLD/V1"
S1_COL = "COPERNICUS/S1_GRD"
CS_THRESHOLD = 0.60
BANDS = ["B2", "B3", "B4", "B8", "B11", "B12"]
NO_DW, NO_S1 = -1.0, -99.0        # valeurs « absent » dans les imagettes

# ---- Plan d'échantillonnage ---- #
# Saisons contrastées : fin des pluies (retenues pleines, végétation inondée, nuages)
# puis saison sèche (décrue, eau turbide, sols nus sombres).
MONTHS = [f"{y}-{m:02d}" for y in (2020, 2022, 2024, 2025) for m in (9, 11)] + \
         [f"{y + 1}-{m:02d}" for y in (2020, 2022, 2024, 2025) for m in (1, 3)]
MONTHS_PER_SITE = 8
MAX_CHIPS_PER_RESERVOIR = 6
N_BACKGROUND = 80
MONTHS_PER_BACKGROUND = 4
BACKGROUND_MIN_DIST_M = 2_000

# ---- Règle d'étiquetage ---- #
MNDWI_WATER, MNDWI_LAND = 0.10, -0.10
DW_WATER, DW_LAND = 0.50, 0.20
WATER, LAND, IGNORE = 1, 0, 255


# --------------------------------------------------------------------------- #
# Où et quand prélever
# --------------------------------------------------------------------------- #
def snap(value: float) -> float:
    """Aligne une coordonnée UTM sur la grille Sentinel-2 (multiples de 10 m)."""
    return float(np.round(value / SCALE_M) * SCALE_M)


def chip_grid(cx: float, cy: float) -> dict:
    """Grille Earth Engine d'une imagette centrée sur (cx, cy), coin haut-gauche aligné à 10 m."""
    return {
        "dimensions": {"width": CHIP, "height": CHIP},
        "affineTransform": {"scaleX": SCALE_M, "shearX": 0, "translateX": snap(cx - CHIP_M / 2),
                            "shearY": 0, "scaleY": -SCALE_M, "translateY": snap(cy + CHIP_M / 2)},
        "crsCode": CRS,
    }


def reservoir_centers(regions_utm, rng: np.random.Generator) -> pd.DataFrame:
    """Centres d'imagettes couvrant la zone d'analyse de chaque retenue.

    Une petite retenue tient dans une imagette centrée ; une grande est pavée, et
    l'on garde au plus `MAX_CHIPS_PER_RESERVOIR` pavés qui touchent sa zone.
    """
    from shapely.geometry import box

    rows = []
    for rid, geom in zip(regions_utm["reservoir_id"], regions_utm.geometry):
        minx, miny, maxx, maxy = geom.bounds
        nx = max(1, int(np.ceil((maxx - minx) / CHIP_M)))
        ny = max(1, int(np.ceil((maxy - miny) / CHIP_M)))
        x0 = (minx + maxx) / 2 - nx * CHIP_M / 2
        y0 = (miny + maxy) / 2 - ny * CHIP_M / 2
        tiles = [(x0 + (i + 0.5) * CHIP_M, y0 + (j + 0.5) * CHIP_M) for i in range(nx) for j in range(ny)]
        tiles = [(x, y) for x, y in tiles
                 if geom.intersects(box(x - CHIP_M / 2, y - CHIP_M / 2, x + CHIP_M / 2, y + CHIP_M / 2))]
        if len(tiles) > MAX_CHIPS_PER_RESERVOIR:
            tiles = [tiles[i] for i in sorted(rng.choice(len(tiles), MAX_CHIPS_PER_RESERVOIR, replace=False))]
        rows += [{"site": rid, "kind": "reservoir", "cx": snap(x), "cy": snap(y)} for x, y in tiles]
    return pd.DataFrame(rows)


def background_centers(regions_utm, n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Lieux tirés au hasard dans la zone d'étude, à distance de toute retenue suivie.

    Ils apportent ce qui ressemble à de l'eau sans en être : ville, sols sombres,
    brûlis, ombres. Sans eux, le réseau ne verrait que des scènes avec une retenue.
    """
    minx, miny, maxx, maxy = regions_utm.total_bounds
    union = regions_utm.geometry.union_all() if hasattr(regions_utm.geometry, "union_all") else regions_utm.unary_union
    keep_out = union.buffer(BACKGROUND_MIN_DIST_M)
    from shapely.geometry import Point

    rows = []
    while len(rows) < n:
        x, y = rng.uniform(minx, maxx), rng.uniform(miny, maxy)
        if not keep_out.contains(Point(x, y)):
            rows.append({"site": f"BG{len(rows):03d}", "kind": "background", "cx": snap(x), "cy": snap(y)})
    return pd.DataFrame(rows)


def assign_split(cx, cy, seed: int = 42) -> np.ndarray:
    """Entraînement / validation / test par blocs de 10 km (70 / 15 / 15 %).

    Séparer par bloc, et non par imagette, évite qu'un même lieu vu à deux dates
    se retrouve à la fois à l'entraînement et au test.
    """
    bx = np.floor(np.asarray(cx) / BLOCK_M).astype(np.int64)
    by = np.floor(np.asarray(cy) / BLOCK_M).astype(np.int64)
    blocks = sorted(set(zip(bx.tolist(), by.tolist())))
    draw = dict(zip(blocks, np.random.default_rng(seed).random(len(blocks))))
    u = np.array([draw[(i, j)] for i, j in zip(bx.tolist(), by.tolist())])
    return np.select([u < 0.70, u < 0.85], ["train", "val"], "test")


def sampling_plan(regions_utm, seed: int = 42) -> pd.DataFrame:
    """Une ligne par imagette à télécharger : lieu, mois, jeu (train / val / test)."""
    rng = np.random.default_rng(seed)
    sites = pd.concat([reservoir_centers(regions_utm, rng),
                       background_centers(regions_utm, N_BACKGROUND, rng)], ignore_index=True)
    sites["split"] = assign_split(sites["cx"], sites["cy"], seed)
    rows = []
    for k, s in enumerate(sites.itertuples(index=False)):
        n = MONTHS_PER_SITE if s.kind == "reservoir" else MONTHS_PER_BACKGROUND
        for month in sorted(rng.choice(MONTHS, n, replace=False)):
            rows.append({"chip_id": f"{s.site}_{k:03d}_{month}", "site": s.site, "kind": s.kind,
                         "cx": s.cx, "cy": s.cy, "month": month, "split": s.split})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Étiquettes
# --------------------------------------------------------------------------- #
def mndwi(x: np.ndarray) -> np.ndarray:
    """Indice d'eau MNDWI = (vert − infrarouge moyen) / (vert + infrarouge moyen), bandes B3 et B11."""
    green, swir = x[BANDS.index("B3")].astype(np.float32), x[BANDS.index("B11")].astype(np.float32)
    return (green - swir) / np.maximum(green + swir, 1e-6)


def make_labels(x: np.ndarray, dw_water: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Étiquettes de consensus : 1 = eau, 0 = pas eau, 255 = ignoré (ambigu, nuage, source absente)."""
    index = mndwi(x)
    known = (valid > 0) & (dw_water >= 0)
    labels = np.full(index.shape, IGNORE, dtype=np.uint8)
    labels[known & (index > MNDWI_WATER) & (dw_water >= DW_WATER)] = WATER
    labels[known & (index < MNDWI_LAND) & (dw_water < DW_LAND)] = LAND
    return labels


def threshold_baseline(x: np.ndarray) -> np.ndarray:
    """Règle opérationnelle actuelle : eau si MNDWI > 0."""
    return mndwi(x) > 0


# --------------------------------------------------------------------------- #
# Téléchargement Earth Engine
# --------------------------------------------------------------------------- #
def month_image(month: str):
    """Image d'un mois : 6 bandes Sentinel-2 (réflectance 0-1), validité, Dynamic World, Sentinel-1."""
    import ee

    start = ee.Date.parse("YYYY-MM", month)
    end = start.advance(1, "month")

    def mask_and_sharpen(im):
        im = im.updateMask(im.select("cs_cdf").gte(CS_THRESHOLD))
        # B11 et B12 (20 m) ramenées sur la grille 10 m, comme pour le MNDWI opérationnel
        return im.addBands(im.select(["B11", "B12"]).resample("bilinear"), overwrite=True)

    s2 = (ee.ImageCollection(S2_COL).filterDate(start, end)
          .linkCollection(ee.ImageCollection(CS_COL), ["cs_cdf"]).map(mask_and_sharpen)
          .select(BANDS).median())
    valid = s2.select("B3").mask().unmask(0).rename("valid")
    dw = ee.ImageCollection(DW_COL).filterDate(start, end).select("water").mean().unmask(NO_DW).rename("dw_water")
    s1 = (ee.ImageCollection(S1_COL).filterDate(start, end)
          .filter(ee.Filter.eq("instrumentMode", "IW"))
          .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
          .select("VV").median().unmask(NO_S1).rename("s1_vv"))
    return ee.Image.cat([s2.divide(10000).unmask(0), valid, dw, s1]).toFloat()


def fetch_chip(image, cx: float, cy: float, retries: int = 4) -> dict[str, np.ndarray]:
    """Télécharge une imagette (avec reprises) et la range en tableaux numpy."""
    import ee

    for attempt in range(retries):
        try:
            arr = ee.data.computePixels({"expression": image, "fileFormat": "NUMPY_NDARRAY",
                                         "grid": chip_grid(cx, cy)})
            break
        except Exception as exc:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            wait = 5 * 2 ** attempt
            logger.warning("GEE : %s -> nouvelle tentative dans %ss", exc, wait)
            time.sleep(wait)
    return {
        "x": np.stack([arr[b] for b in BANDS]).astype(np.float16),
        "valid": arr["valid"].astype(np.uint8),
        "dw_water": arr["dw_water"].astype(np.float16),
        "s1_vv": arr["s1_vv"].astype(np.float16),
    }


def extract(out_dir: Path, regions_path: Path, workers: int = 8, limit: int | None = None, seed: int = 42) -> pd.DataFrame:
    """Télécharge les imagettes du plan dans `out_dir` (reprend là où une exécution s'est arrêtée)."""
    import geopandas as gpd

    regions = gpd.read_file(regions_path).to_crs(CRS)
    plan = sampling_plan(regions, seed)
    if limit:
        plan = plan.sample(limit, random_state=seed).reset_index(drop=True)
    chips_dir = out_dir / "chips"
    chips_dir.mkdir(parents=True, exist_ok=True)
    images = {month: month_image(month) for month in plan["month"].unique()}

    def one(row) -> tuple[str, dict]:
        path = chips_dir / f"{row.chip_id}.npz"
        chip = None
        if path.exists():
            try:
                chip = dict(np.load(path))
            except Exception:  # noqa: BLE001 - fichier tronqué par une exécution interrompue
                logger.warning("Imagette %s illisible : nouveau téléchargement", row.chip_id)
        if chip is None:
            chip = fetch_chip(images[row.month], row.cx, row.cy)
            # Écriture dans un fichier provisoire puis renommage : jamais de fichier à moitié écrit
            tmp = chips_dir / f"{row.chip_id}.part.npz"
            np.savez_compressed(tmp, **chip)
            tmp.replace(path)
        labels = make_labels(chip["x"].astype(np.float32), chip["dw_water"].astype(np.float32), chip["valid"])
        return row.chip_id, {"valid_frac": float(chip["valid"].mean()),
                             "water_frac": float((labels == WATER).mean()),
                             "land_frac": float((labels == LAND).mean()),
                             "ignore_frac": float((labels == IGNORE).mean()),
                             "has_dw": bool((chip["dw_water"] >= 0).any()),
                             "has_s1": bool((chip["s1_vv"] > NO_S1).any())}

    stats, failed = {}, []
    with ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(one, row): row.chip_id for row in plan.itertuples(index=False)}
        for done, future in enumerate(as_completed(futures), 1):
            try:
                chip_id, info = future.result()
                stats[chip_id] = info
            except Exception as exc:  # noqa: BLE001
                failed.append(futures[future])
                logger.error("Imagette %s abandonnée : %s", futures[future], exc)
            if done % 100 == 0:
                logger.info("%d / %d imagettes", done, len(plan))
    manifest = plan.join(pd.DataFrame.from_dict(stats, orient="index"), on="chip_id")
    manifest = manifest[manifest["valid_frac"].notna()].reset_index(drop=True)
    manifest.to_csv(out_dir / "manifest.csv", index=False)
    logger.info("%d imagettes enregistrées, %d abandonnées -> %s", len(manifest), len(failed), out_dir)
    return manifest


def main() -> None:
    import sys

    backend = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(backend))
    parser = argparse.ArgumentParser(description="Extrait les imagettes Sentinel-2 pour le modèle de détection de l'eau")
    parser.add_argument("--out", type=Path, default=backend / "data" / "unet")
    parser.add_argument("--regions", type=Path, default=backend / "data" / "gee" / "analysis_regions.geojson")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=None, help="nombre d'imagettes (essai rapide)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    from app.collectors.earth_engine import EarthEngineClient

    EarthEngineClient().initialize()
    # Une imagette se calcule en quelques secondes : au-delà d'une minute, la requête est
    # bloquée et doit être retentée (le client règle sinon 10 minutes par requête).
    import ee
    ee.data.setDeadline(60_000)
    manifest = extract(args.out, args.regions, args.workers, args.limit)
    print(manifest.groupby(["split", "kind"]).size().unstack(fill_value=0))
    print(manifest[["valid_frac", "water_frac", "land_frac", "ignore_frac"]].describe().round(3))


if __name__ == "__main__":
    main()
