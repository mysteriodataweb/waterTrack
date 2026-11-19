"""Tests de l'inventaire automatique (ml/unet_inventory.py) sur une carte synthétique, sans Earth Engine ni réseau."""
import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import box

import ml.unet_data as U
import ml.unet_inventory as I

GRID = {"x0": 600_000.0, "y1": 1_400_000.0, "nx": 2, "ny": 1}


def mosaic_with(blocks: list[tuple[int, int, int, int]]) -> dict:
    """Carte de 128 × 256 pixels avec des rectangles d'eau (ligne, colonne, hauteur, largeur)."""
    shape = (GRID["ny"] * U.CHIP, GRID["nx"] * U.CHIP)
    water = np.zeros(shape, dtype=bool)
    for r, c, h, w in blocks:
        water[r:r + h, c:c + w] = True
    return {"unet": water, "rule": water.copy(), "valid": np.ones(shape, bool), "dark": water.copy(),
            "has_s1": np.ones(shape, bool), "prob": (water * 90).astype(np.uint8)}


def test_tile_grid_covers_the_bounds_and_is_aligned():
    grid = I.tile_grid((600_003.0, 1_350_000.0, 612_000.0, 1_360_000.0), margin_m=1_000)
    assert grid["x0"] % 10 == 0 and grid["y1"] % 10 == 0
    assert grid["x0"] <= 599_003 and grid["x0"] + grid["nx"] * U.CHIP_M >= 613_000
    assert grid["y1"] >= 1_361_000 and grid["y1"] - grid["ny"] * U.CHIP_M <= 1_349_000
    cx, cy = I.tile_center(grid, 0, 0)
    assert cx == grid["x0"] + 640 and cy == grid["y1"] - 640


def test_water_bodies_keep_large_components_with_the_right_area_and_place():
    # 10 × 10 pixels = 1 ha ; 3 × 3 pixels = 0,09 ha (écarté) ; un plan d'eau à cheval sur deux pavés
    bodies = I.water_bodies(mosaic_with([(10, 10, 10, 10), (60, 60, 3, 3), (100, 120, 8, 16)]), GRID)
    assert sorted(bodies["area_ha"]) == [1.0, 1.28]
    one_ha = bodies[bodies["area_ha"] == 1.0].iloc[0]
    assert one_ha.geometry.bounds == pytest.approx((600_100, 1_399_800, 600_200, 1_399_900))
    assert one_ha.geometry.area == pytest.approx(10_000)
    assert one_ha["mean_prob"] == 0.9 and one_ha["radar_dark"] == 1.0 and one_ha["rule_share"] == 1.0
    assert one_ha["compactness"] == pytest.approx(np.pi / 4, abs=0.01)       # carré


def test_diagonal_pixels_belong_to_the_same_water_body():
    water = mosaic_with([])
    for k in range(60):
        water["unet"][k, k] = True
    bodies = I.water_bodies(water, GRID)
    assert len(bodies) == 1 and bodies.iloc[0]["area_ha"] == 0.6


def test_match_known_separates_followed_reservoirs_from_candidates():
    bodies = I.water_bodies(mosaic_with([(10, 10, 10, 10), (80, 200, 10, 10)]), GRID)
    regions = gpd.GeoDataFrame(
        {"reservoir_id": ["R01", "R02"]},
        geometry=[box(600_050, 1_399_750, 600_250, 1_399_950),      # entoure le premier plan d'eau
                  box(601_500, 1_399_800, 601_600, 1_399_900)],     # aucune eau détectée ici
        crs=U.CRS)
    matched, known = I.match_known(bodies, regions)
    assert matched["is_new"].sum() == 1 and set(matched["known_ids"]) == {"R01", ""}
    assert known.set_index("reservoir_id")["found"].to_dict() == {"R01": True, "R02": False}
    assert known.set_index("reservoir_id")["detected_ha"]["R01"] == 1.0


def test_no_water_gives_an_empty_inventory():
    bodies = I.water_bodies(mosaic_with([]), GRID)
    assert len(bodies) == 0
