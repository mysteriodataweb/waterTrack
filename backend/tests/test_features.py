"""Tests du module ml/features.py (modèle v3) : absence de fuite temporelle."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml import features as F


@pytest.fixture
def toy_panel() -> pd.DataFrame:
    """Deux réservoirs, 48 mois, cycle saisonnier synthétique."""
    rng = np.random.default_rng(0)
    dates = pd.date_range("2019-01-01", periods=48, freq="MS")
    rows = []
    for rid in ("R01", "R02"):
        season = 0.5 + 0.4 * np.sin(2 * np.pi * (dates.month - 4) / 12)
        for d, f in zip(dates, season + rng.normal(0, 0.03, len(dates))):
            rows.append({
                "reservoir_id": rid, "date": d, "fill": float(f), "area_source": "S2",
                "precip_mm": float(max(0, 100 * np.sin(2 * np.pi * (d.month - 4) / 12))),
                "pet_mm": 350.0, "aet_mm": 40.0, "t2m_c": 29.0, "soil_moist": 0.2,
            })
    return pd.DataFrame(rows)


@pytest.fixture
def static() -> pd.DataFrame:
    reservoirs = pd.DataFrame({
        "reservoir_id": ["R01", "R02"], "a_ref_ha": [100.0, 20.0],
        "jrc_occ_mean": [60.0, 30.0], "jrc_seasonality": [8.0, 5.0],
        "elev_m": [280.0, 300.0], "slope_deg": [1.0, 2.0],
        "basin_km2": [150.0, 200.0], "upstream_km2": [300.0, 400.0],
    })
    return F.static_features(reservoirs)


def test_features_do_not_use_future_values(toy_panel, static):
    """Modifier les mois postérieurs à t ne doit changer aucune variable émise à t."""
    clim = F.fit_climatology(toy_panel, "2020-12")
    issue = pd.Timestamp("2021-06-01")

    base = F.build_rows(toy_panel, 2, clim, static, with_target=False)
    altered_panel = toy_panel.copy()
    future = altered_panel["date"] > issue
    altered_panel.loc[future, ["fill", "precip_mm"]] = 99.0
    altered = F.build_rows(altered_panel, 2, clim, static, with_target=False)

    pick = lambda d: d[d["date"] == issue].set_index("reservoir_id")[F.FEATURES].sort_index()
    pd.testing.assert_frame_equal(pick(base), pick(altered))


def test_target_is_shifted_by_horizon(toy_panel, static):
    clim = F.fit_climatology(toy_panel, "2020-12")
    rows = F.build_rows(toy_panel, 3, clim, static)
    r = rows[rows["reservoir_id"] == "R01"].reset_index(drop=True)
    src = toy_panel[toy_panel["reservoir_id"] == "R01"].reset_index(drop=True)
    assert r.loc[10, "y"] == pytest.approx(src.loc[13, "fill"])
    assert r.loc[10, "target_date"] == src.loc[13, "date"]


def test_leave_one_year_out_climatology_excludes_target_year(toy_panel, static):
    """En entraînement, clim_target ne doit pas contenir la valeur de la cible elle-même."""
    panel = toy_panel.copy()
    spike = (panel["reservoir_id"] == "R01") & (panel["date"] == "2019-07-01")
    panel.loc[spike, "fill"] = 50.0  # valeur aberrante : la médiane avec elle changerait peu, sans elle pas du tout
    clim = F.fit_climatology(panel, "2020-12")
    rows = F.build_rows(panel, 1, clim, static, train_end="2020-12")
    row = rows[(rows["reservoir_id"] == "R01") & (rows["target_date"] == "2019-07-01")].iloc[0]
    other_year = panel[(panel["reservoir_id"] == "R01") & (panel["date"] == "2020-07-01")]["fill"].iloc[0]
    assert row["clim_target"] == pytest.approx(other_year)


def test_feature_list_is_complete(toy_panel, static):
    clim = F.fit_climatology(toy_panel, "2020-12")
    rows = F.build_rows(toy_panel, 1, clim, static)
    assert set(F.FEATURES) <= set(rows.columns)
