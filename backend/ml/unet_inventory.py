"""
Inventaire automatique des plans d'eau avec le U-Net.

Le réseau est appliqué à TOUTE la zone d'étude pour un mois donné (pavage en
imagettes de 1,28 km). Les pixels « eau » voisins sont regroupés en plans d'eau,
puis comparés aux retenues déjà suivies :
  - combien de retenues connues sont retrouvées (contrôle de l'inventaire) ;
  - quels plans d'eau ne correspondent à aucune retenue suivie (candidats).

Un candidat n'est pas une retenue confirmée : cela peut être un tronçon de
rivière, une mare temporaire, une carrière en eau ou une fausse détection. La
liste est faite pour être vérifiée (image, terrain), pas pour être intégrée telle quelle.

Usage :
  python -m ml.unet_inventory --month 2025-11
"""
from __future__ import annotations

import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

from . import unet_data as U

logger = logging.getLogger("unet_inventory")

MIN_AREA_HA = 0.5                 # plus petit plan d'eau retenu (50 pixels de 10 m)
PIXEL_HA = U.SCALE_M ** 2 / 1e4
S1_DARK_DB = -18.0


# --------------------------------------------------------------------------- #
# Pavage de la zone
# --------------------------------------------------------------------------- #
def tile_grid(bounds: tuple[float, float, float, float], margin_m: float = 1_000) -> dict:
    """Pavage régulier couvrant `bounds` (UTM) : origine haut-gauche alignée à 10 m, nombre de pavés."""
    minx, miny, maxx, maxy = bounds
    x0, y1 = U.snap(minx - margin_m), U.snap(maxy + margin_m)
    nx = int(np.ceil((maxx + margin_m - x0) / U.CHIP_M))
    ny = int(np.ceil((y1 - (miny - margin_m)) / U.CHIP_M))
    return {"x0": x0, "y1": y1, "nx": nx, "ny": ny}


def tile_center(grid: dict, i: int, j: int) -> tuple[float, float]:
    """Centre du pavé colonne i, ligne j (ligne 0 au nord)."""
    return grid["x0"] + (i + 0.5) * U.CHIP_M, grid["y1"] - (j + 0.5) * U.CHIP_M


def download_tiles(grid: dict, month: str, out_dir: Path, workers: int = 8) -> int:
    """Télécharge tous les pavés du mois (reprend une exécution interrompue). Renvoie le nombre d'échecs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    image = U.month_image(month)
    todo = [(i, j) for j in range(grid["ny"]) for i in range(grid["nx"]) if not (out_dir / f"t_{j:03d}_{i:03d}.npz").exists()]
    logger.info("%d pavés à télécharger sur %d", len(todo), grid["nx"] * grid["ny"])

    def one(i: int, j: int) -> None:
        chip = U.fetch_chip(image, *tile_center(grid, i, j))
        tmp = out_dir / f"t_{j:03d}_{i:03d}.part.npz"
        np.savez_compressed(tmp, **chip)
        tmp.replace(out_dir / f"t_{j:03d}_{i:03d}.npz")

    failed = 0
    with ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(one, i, j) for i, j in todo]
        for done, future in enumerate(as_completed(futures), 1):
            try:
                future.result()
            except Exception as exc:  # noqa: BLE001
                failed += 1
                logger.error("Pavé abandonné : %s", exc)
            if done % 500 == 0:
                logger.info("%d / %d pavés", done, len(todo))
    return failed


def predict_mosaic(grid: dict, tiles_dir: Path, model, mean, std, batch: int = 64) -> dict[str, np.ndarray]:
    """Assemble les cartes de toute la zone : eau selon le réseau, selon la règle MNDWI, validité, radar sombre."""
    from . import unet_model as M

    h, w = grid["ny"] * U.CHIP, grid["nx"] * U.CHIP
    mosaic = {k: np.zeros((h, w), dtype=bool) for k in ("unet", "rule", "valid", "dark", "has_s1")}
    prob = np.zeros((h, w), dtype=np.uint8)                      # probabilité en pourcentage
    keys = [(i, j) for j in range(grid["ny"]) for i in range(grid["nx"]) if (tiles_dir / f"t_{j:03d}_{i:03d}.npz").exists()]
    for start in range(0, len(keys), batch):
        part = keys[start:start + batch]
        chips = [np.load(tiles_dir / f"t_{j:03d}_{i:03d}.npz") for i, j in part]
        x = np.stack([c["x"].astype(np.float32) for c in chips])
        p = M.predict(model, x, mean, std, batch=batch)
        for (i, j), chip, xi, pi in zip(part, chips, x, p):
            rows, cols = slice(j * U.CHIP, (j + 1) * U.CHIP), slice(i * U.CHIP, (i + 1) * U.CHIP)
            valid = chip["valid"] > 0
            s1 = chip["s1_vv"].astype(np.float32)
            mosaic["valid"][rows, cols] = valid
            mosaic["unet"][rows, cols] = (pi > 0.5) & valid
            mosaic["rule"][rows, cols] = U.threshold_baseline(xi) & valid
            mosaic["has_s1"][rows, cols] = s1 > U.NO_S1
            mosaic["dark"][rows, cols] = (s1 > U.NO_S1) & (s1 < S1_DARK_DB)
            prob[rows, cols] = np.round(pi * 100)
    mosaic["prob"] = prob
    return mosaic


# --------------------------------------------------------------------------- #
# Des pixels aux plans d'eau
# --------------------------------------------------------------------------- #
def component_polygon(rows: np.ndarray, cols: np.ndarray, grid: dict):
    """Contour d'un plan d'eau à partir de ses pixels (union de bandes horizontales)."""
    from shapely.geometry import box
    from shapely.ops import unary_union

    boxes = []
    order = np.lexsort((cols, rows))
    rows, cols = rows[order], cols[order]
    breaks = np.flatnonzero((np.diff(rows) != 0) | (np.diff(cols) != 1)) + 1
    for seg_r, seg_c in zip(np.split(rows, breaks), np.split(cols, breaks)):
        y_top = grid["y1"] - seg_r[0] * U.SCALE_M
        boxes.append(box(grid["x0"] + seg_c[0] * U.SCALE_M, y_top - U.SCALE_M,
                         grid["x0"] + (seg_c[-1] + 1) * U.SCALE_M, y_top))
    return unary_union(boxes)


def water_bodies(mosaic: dict[str, np.ndarray], grid: dict, min_area_ha: float = MIN_AREA_HA):
    """Regroupe les pixels « eau » voisins (8 voisins) en plans d'eau d'au moins `min_area_ha`."""
    import geopandas as gpd
    from scipy import ndimage

    labels, n = ndimage.label(mosaic["unet"], structure=np.ones((3, 3), dtype=bool))
    rows_out = []
    for k, sl in enumerate(ndimage.find_objects(labels), 1):
        inside = labels[sl] == k
        area_ha = float(inside.sum() * PIXEL_HA)
        if area_ha < min_area_ha:
            continue
        r, c = np.nonzero(inside)
        r, c = r + sl[0].start, c + sl[1].start
        geom = component_polygon(r, c, grid)
        has_s1 = mosaic["has_s1"][r, c]
        rows_out.append({
            "area_ha": round(area_ha, 2),
            "mean_prob": round(float(mosaic["prob"][r, c].mean()) / 100, 3),
            # Part du plan d'eau que la règle opérationnelle MNDWI > 0 classe aussi en eau
            "rule_share": round(float(mosaic["rule"][r, c].mean()), 3),
            # Part sombre au radar (indice indépendant d'eau libre) ; None si pas de radar
            "radar_dark": round(float(mosaic["dark"][r, c][has_s1].mean()), 3) if has_s1.any() else None,
            # 1 = disque, proche de 0 = forme très allongée (rivière, bord de pavé)
            "compactness": round(float(4 * np.pi * geom.area / geom.length ** 2), 3),
            "geometry": geom,
        })
    bodies = gpd.GeoDataFrame(rows_out, geometry="geometry", crs=U.CRS) if rows_out else \
        gpd.GeoDataFrame({"area_ha": []}, geometry=[], crs=U.CRS)
    return bodies.sort_values("area_ha", ascending=False).reset_index(drop=True)


def match_known(bodies, regions_utm):
    """Rattache chaque plan d'eau aux retenues suivies qu'il touche.

    Renvoie (plans d'eau avec `known_ids`, tableau par retenue connue : surface détectée dans sa zone).
    """
    import geopandas as gpd

    bodies = bodies.copy()
    pairs = gpd.sjoin(bodies[["geometry"]], regions_utm[["reservoir_id", "geometry"]], predicate="intersects")
    ids = pairs.groupby(level=0)["reservoir_id"].agg(lambda s: ",".join(sorted(s)))
    bodies["known_ids"] = ids.reindex(bodies.index).fillna("")
    bodies["is_new"] = bodies["known_ids"] == ""
    union = bodies.geometry.union_all() if len(bodies) else None
    detected = regions_utm.geometry.apply(lambda g: g.intersection(union).area / 1e4 if union is not None else 0.0)
    known = pd.DataFrame({"reservoir_id": regions_utm["reservoir_id"].to_numpy(), "detected_ha": detected.round(2).to_numpy()})
    known["found"] = known["detected_ha"] >= MIN_AREA_HA
    return bodies, known


def main() -> None:
    import sys

    import geopandas as gpd

    backend = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(backend))
    parser = argparse.ArgumentParser(description="Inventaire automatique des plans d'eau (U-Net)")
    parser.add_argument("--month", default="2025-11", help="mois analysé, AAAA-MM (novembre : retenues pleines, peu de nuages)")
    parser.add_argument("--model", type=Path, default=backend / "ml" / "runs" / "unet_latest" / "model.pt")
    parser.add_argument("--regions", type=Path, default=backend / "data" / "gee" / "analysis_regions.geojson")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    out = args.out or backend / "data" / "unet" / f"inventory_{args.month}"

    from app.collectors.earth_engine import EarthEngineClient

    from . import unet_model as M

    regions = gpd.read_file(args.regions).to_crs(U.CRS)
    grid = tile_grid(tuple(regions.total_bounds))
    EarthEngineClient().initialize()
    failed = download_tiles(grid, args.month, out / "tiles", args.workers)
    model, mean, std, _ = M.load_model(args.model)
    mosaic = predict_mosaic(grid, out / "tiles", model, mean, std)
    bodies, known = match_known(water_bodies(mosaic, grid), regions)

    bodies.to_crs(4326).to_file(out / "water_bodies.geojson", driver="GeoJSON")
    known.to_csv(out / "known_reservoirs.csv", index=False)
    new = bodies[bodies["is_new"]]
    summary = {
        "month": args.month, "tiles": grid["nx"] * grid["ny"], "tiles_failed": failed,
        "valid_share": float(mosaic["valid"].mean()),
        "water_ha_unet": float(mosaic["unet"].sum() * PIXEL_HA), "water_ha_rule": float(mosaic["rule"].sum() * PIXEL_HA),
        "n_bodies": int(len(bodies)), "n_new": int(len(new)), "new_area_ha": float(new["area_ha"].sum()),
        "n_known": int(len(known)), "n_known_found": int(known["found"].sum()),
        "known_not_found": known.loc[~known["found"], "reservoir_id"].tolist(),
        "new_by_size": {"0.5-1 ha": int((new["area_ha"] < 1).sum()), "1-5 ha": int(new["area_ha"].between(1, 5, inclusive="left").sum()),
                        "5 ha et plus": int((new["area_ha"] >= 5).sum())},
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(new.drop(columns="geometry").head(15).to_string())


if __name__ == "__main__":
    main()
