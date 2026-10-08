"""Tests du backend v3 : collecte (fusion), panel, bulletin, et intégration API sur la base locale."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.collectors.water_area import area_to_volume_m3, fuse, s1_threshold_from_column
from app.services.reservoirs import _none, bulletin_to_csv, complete_grid


# --------------------------------------------------------------------------- #
# Fusion Sentinel-2 / Sentinel-1
# --------------------------------------------------------------------------- #
@pytest.fixture
def fusion_inputs():
    s2 = pd.DataFrame({
        "reservoir_id": ["A", "B", "C"],
        "water_m2": [50e4, 10e4, 5e4],
        "valid_m2": [100e4, 50e4, 50e4],      # A : 100 % valide ; B et C : 50 % (nuageux)
        "region_m2": [100e4, 100e4, 100e4],
    })
    s1 = pd.DataFrame({"reservoir_id": ["A", "B", "C"], "s1_water_m2": [40e4, 30e4, 30e4]})
    mapping = pd.DataFrame({"a": [0.0, 2.0, 0.0], "b": [1.0, 1.5, 1.0], "usable": [True, True, False]},
                           index=["A", "B", "C"])
    a_ref = pd.Series({"A": 100.0, "B": 50.0, "C": 20.0})
    return s2, s1, mapping, a_ref


def test_fuse_prefers_reliable_optical(fusion_inputs):
    out = fuse(*fusion_inputs).set_index("reservoir_id")
    assert out.loc["A", "area_source"] == "S2"
    assert out.loc["A", "area_ha"] == pytest.approx(50.0)
    assert out.loc["A", "fill"] == pytest.approx(0.5)


def test_fuse_uses_calibrated_radar_when_cloudy(fusion_inputs):
    out = fuse(*fusion_inputs).set_index("reservoir_id")
    assert out.loc["B", "area_source"] == "S1"
    assert out.loc["B", "area_ha"] == pytest.approx(2.0 + 1.5 * 30.0)


def test_fuse_marks_missing_without_usable_radar(fusion_inputs):
    out = fuse(*fusion_inputs).set_index("reservoir_id")
    assert out.loc["C", "area_source"] == "manquant"
    assert np.isnan(out.loc["C", "fill"])


def test_fill_is_capped(fusion_inputs):
    s2, s1, mapping, a_ref = fusion_inputs
    out = fuse(s2, s1, mapping, a_ref * 0.01).set_index("reservoir_id")
    assert out.loc["A", "fill"] == pytest.approx(1.5)


def test_volume_only_within_liebe_range(fusion_inputs):
    s2, s1, mapping, a_ref = fusion_inputs
    out = fuse(s2, s1, mapping, a_ref).set_index("reservoir_id")
    assert np.isnan(out.loc["A", "volume_m3"])       # A_ref = 100 ha : hors domaine (1-35 ha)
    in_range = fuse(s2, s1, mapping, pd.Series({"A": 30.0, "B": 50.0, "C": 20.0})).set_index("reservoir_id")
    assert in_range.loc["A", "volume_m3"] == pytest.approx(area_to_volume_m3(50.0))
    assert area_to_volume_m3(10.0) == pytest.approx(0.00857 * 1e5 ** 1.4367)


def test_s1_threshold_parsed_from_column():
    assert s1_threshold_from_column("s1_water_20_ha") == -20.0
    assert s1_threshold_from_column("s1_water_18_ha") == -18.0


# --------------------------------------------------------------------------- #
# Panel et bulletin
# --------------------------------------------------------------------------- #
def test_complete_grid_inserts_missing_months():
    df = pd.DataFrame({
        "reservoir_id": ["A", "A", "B"],
        "date": ["2024-01-01", "2024-03-01", "2024-02-01"],
        "fill": [0.5, 0.3, 0.8],
        "area_source": ["S2", "S2", "S1"],
    })
    out = complete_grid(df)
    assert len(out) == 6                                   # 2 réservoirs × 3 mois
    gap = out[(out.reservoir_id == "A") & (out.date == "2024-02-01")].iloc[0]
    assert np.isnan(gap["fill"]) and gap["area_source"] == "manquant"


def test_none_converts_numpy_and_nan():
    assert _none(np.float64("nan")) is None
    assert _none(np.float64(1.5)) == 1.5 and type(_none(np.float64(1.5))) is float
    assert _none(np.int64(3)) == 3 and type(_none(np.int64(3))) is int
    assert _none("S2") == "S2"


def test_bulletin_csv_flattens_horizons():
    bulletin = {"reservoirs": [{
        "reservoir_id": "R05", "origin": "application", "source_ids": [5, 6], "fill_now": 0.4,
        "status": "actif", "forecast": [
            {"horizon": 1, "fill_pred": 0.35, "fill_lo80": 0.2, "fill_hi80": 0.5, "p_critical": 0.1},
            {"horizon": 2, "fill_pred": 0.3, "fill_lo80": 0.1, "fill_hi80": 0.5, "p_critical": 0.2},
        ],
    }]}
    csv = pd.read_csv(pd.io.common.StringIO(bulletin_to_csv(bulletin)))
    assert csv.loc[0, "source_ids"] == "5 6"
    assert csv.loc[0, "p_critical_h2"] == pytest.approx(0.2)


# --------------------------------------------------------------------------- #
# Intégration : API sur la base locale (ignorée si la base ou les données v3 manquent)
# --------------------------------------------------------------------------- #
def _v3_ready() -> bool:
    try:
        from sqlalchemy import text
        from app.database import engine
        with engine.connect() as conn:
            return bool(conn.execute(text("SELECT count(*) FROM fill_forecasts")).scalar())
    except Exception:  # noqa: BLE001
        return False


v3 = pytest.mark.skipif(not _v3_ready(), reason="base locale ou données v3 absentes (scripts/load_v3.py)")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


@v3
def test_api_reservoirs_and_history(client):
    res = client.get("/api/reservoirs").json()
    assert len(res) > 0 and {"application", "JRC"} >= {r["origin"] for r in res}
    rid = next(r["id"] for r in res if r["modelable"])
    hist = client.get(f"/api/reservoirs/{rid}/history?start=2024-01").json()
    assert hist["points"] and all(p["month"] >= "2024-01" for p in hist["points"])


@v3
def test_api_forecast_for_source_and_reservoir(client):
    res = client.get("/api/reservoirs?origin=application").json()
    linked = next(r for r in res if r["source_ids"] and r["modelable"])
    by_source = client.get(f"/api/water-sources/{linked['source_ids'][0]}/forecast")
    assert by_source.status_code == 200
    body = by_source.json()
    assert body["reservoir_id"] == linked["id"]
    assert [h["horizon"] for h in body["horizons"]] == sorted(h["horizon"] for h in body["horizons"])
    for h in body["horizons"]:
        assert h["fill_lo80"] <= h["fill_hi80"]
        assert 0 <= h["p_critical"] <= 1


@v3
def test_api_bulletin_json_and_csv(client):
    b = client.get("/api/bulletin").json()
    assert b["n_reservoirs"] == len(b["reservoirs"]) > 0
    p = [r["p_critical_max"] for r in b["reservoirs"]]
    assert p == sorted(p, reverse=True)                     # classé par risque décroissant
    csv = client.get("/api/bulletin?format=csv")
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")


@v3
def test_api_validation_requires_key_and_roundtrips(client):
    from app.config import settings
    rid = client.get("/api/reservoirs?origin=JRC").json()[0]["id"]
    settings.api_key = "test-key"
    try:
        assert client.patch(f"/api/admin/reservoirs/{rid}/validation", json={"validation": "valide"}).status_code == 401
        r = client.patch(f"/api/admin/reservoirs/{rid}/validation", headers={"X-API-Key": "test-key"},
                         json={"validation": "rejete", "note": "test automatique"})
        assert r.status_code == 200 and r.json()["validation"] == "rejete"
        assert rid not in {x["reservoir_id"] for x in client.get("/api/bulletin").json()["reservoirs"]}
    finally:
        client.patch(f"/api/admin/reservoirs/{rid}/validation", headers={"X-API-Key": "test-key"},
                     json={"validation": "a_valider", "note": None})
        settings.api_key = "change-me-in-production"
