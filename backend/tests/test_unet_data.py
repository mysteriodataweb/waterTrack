"""Tests de la préparation des données du modèle de détection de l'eau (ml/unet_data.py), sans Earth Engine."""
import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import box

import ml.unet_data as U


def regions(sizes_m: list[float]) -> gpd.GeoDataFrame:
    """Zones carrées de côtés donnés, espacées de 30 km en UTM 30N."""
    geoms = [box(600_000 + 30_000 * i, 1_350_000, 600_000 + 30_000 * i + s, 1_350_000 + s) for i, s in enumerate(sizes_m)]
    return gpd.GeoDataFrame({"reservoir_id": [f"R{i:02d}" for i in range(len(sizes_m))]}, geometry=geoms, crs=U.CRS)


def chip(green: float, swir: float) -> np.ndarray:
    x = np.full((len(U.BANDS), 4, 4), 0.1, dtype=np.float32)
    x[U.BANDS.index("B3")], x[U.BANDS.index("B11")] = green, swir
    return x


def test_chip_grid_is_aligned_on_the_sentinel_grid():
    grid = U.chip_grid(660_003.0, 1_368_004.0)
    t = grid["affineTransform"]
    assert t["translateX"] % 10 == 0 and t["translateY"] % 10 == 0
    assert (t["scaleX"], t["scaleY"]) == (10, -10)
    assert grid["dimensions"] == {"width": 128, "height": 128} and grid["crsCode"] == "EPSG:32630"
    # L'imagette est centrée : son coin haut-gauche est à une demi-imagette du centre
    assert t["translateX"] == pytest.approx(660_003.0 - 640, abs=5)
    assert t["translateY"] == pytest.approx(1_368_004.0 + 640, abs=5)


def test_small_reservoir_gets_one_centred_chip_and_large_one_is_capped():
    r = regions([600.0, 20_000.0])
    centers = U.reservoir_centers(r, np.random.default_rng(0))
    small = centers[centers["site"] == "R00"]
    assert len(small) == 1
    assert small.iloc[0]["cx"] == pytest.approx(600_300.0, abs=5) and small.iloc[0]["cy"] == pytest.approx(1_350_300.0, abs=5)
    assert (centers["site"] == "R01").sum() == U.MAX_CHIPS_PER_RESERVOIR


def test_background_centers_stay_away_from_reservoirs():
    r = regions([1_000.0, 1_000.0, 1_000.0])
    bg = U.background_centers(r, 25, np.random.default_rng(1))
    assert len(bg) == 25 and (bg["kind"] == "background").all()
    points = gpd.GeoSeries(gpd.points_from_xy(bg["cx"], bg["cy"]), crs=U.CRS)
    nearest = points.apply(lambda p: r.distance(p).min())
    assert (nearest >= U.BACKGROUND_MIN_DIST_M - 10).all()


def test_split_keeps_a_place_in_a_single_set():
    plan = U.sampling_plan(regions([800.0] * 12))
    assert set(plan["split"]) <= {"train", "val", "test"}
    assert (plan.groupby("site")["split"].nunique() == 1).all()
    # Même bloc de 10 km -> même jeu, quelle que soit la date
    block = (plan["cx"] // U.BLOCK_M).astype(int).astype(str) + "_" + (plan["cy"] // U.BLOCK_M).astype(int).astype(str)
    assert (plan.groupby(block)["split"].nunique() == 1).all()
    assert plan["chip_id"].is_unique
    assert (plan[plan["kind"] == "reservoir"].groupby("site")["month"].nunique() == U.MONTHS_PER_SITE).all()
    assert plan.equals(U.sampling_plan(regions([800.0] * 12)))      # plan reproductible


def test_labels_need_both_sources_to_agree():
    water, land, edge = chip(0.10, 0.02), chip(0.05, 0.25), chip(0.10, 0.10)   # MNDWI 0,67 / −0,67 / 0
    ones, yes, no = np.ones((4, 4), np.uint8), np.full((4, 4), 0.9, np.float32), np.full((4, 4), 0.05, np.float32)
    assert (U.make_labels(water, yes, ones) == U.WATER).all()
    assert (U.make_labels(land, no, ones) == U.LAND).all()
    assert (U.make_labels(water, no, ones) == U.IGNORE).all()      # indice dit eau, Dynamic World dit non
    assert (U.make_labels(land, yes, ones) == U.IGNORE).all()
    assert (U.make_labels(edge, yes, ones) == U.IGNORE).all()      # indice ambigu


def test_labels_ignore_clouds_and_missing_dynamic_world():
    water = chip(0.10, 0.02)
    yes = np.full((4, 4), 0.9, np.float32)
    cloudy = np.ones((4, 4), np.uint8)
    cloudy[0] = 0
    labels = U.make_labels(water, yes, cloudy)
    assert (labels[0] == U.IGNORE).all() and (labels[1:] == U.WATER).all()
    missing = np.full((4, 4), U.NO_DW, np.float32)
    assert (U.make_labels(water, missing, np.ones((4, 4), np.uint8)) == U.IGNORE).all()


def test_threshold_baseline_is_the_operational_rule():
    assert U.threshold_baseline(chip(0.10, 0.02)).all()
    assert not U.threshold_baseline(chip(0.05, 0.25)).any()
