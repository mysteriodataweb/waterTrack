"""Tests de la détection des prélèvements anormaux (ml/withdrawals.py) sur un panel synthétique."""
import numpy as np
import pandas as pd
import pytest

import ml.withdrawals as W


def make_panel(n_reservoirs: int = 12, n_seasons: int = 5, monthly_drop: float = 500.0,
               noise: float = 30.0, seed: int = 0) -> pd.DataFrame:
    """Retenues qui perdent `monthly_drop` mm d'indice de niveau par mois d'octobre à mai."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2019-07-01", periods=12 * n_seasons, freq="MS")
    frames = []
    for i in range(n_reservoirs):
        a_ref = 15.0 + 3 * i
        top = W.level_mm(a_ref)
        months_dry = (dates.month - 10) % 12                      # octobre = 0 … septembre = 11
        level = np.where(months_dry <= 7, top - monthly_drop * months_dry, top * 0.6)
        level = np.clip(level + rng.normal(0, noise, len(dates)), 0, None)
        area = W.area_from_level(level)
        frames.append(pd.DataFrame({
            "reservoir_id": f"R{i:02d}", "date": dates, "area_ha": area, "fill": area / a_ref, "a_ref_ha": a_ref,
            "precip_mm": np.where(dates.month.isin([6, 7, 8, 9]), 150.0, 0.0), "pet_mm": 380.0,
            "area_source": "S2", "outlier": False,
        }))
    return pd.concat(frames, ignore_index=True)


def test_level_and_area_are_inverse():
    area = np.array([0.0, 1.0, 12.5, 400.0])
    assert W.area_from_level(W.level_mm(area)) == pytest.approx(area)
    assert W.level_mm(0.0) == 0


def test_monthly_drops_keeps_only_dry_measured_months():
    panel = make_panel(n_reservoirs=2, noise=0.0)
    panel.loc[(panel["reservoir_id"] == "R00") & (panel["date"] == "2020-01-01"), "area_source"] = "S1"
    drops = W.monthly_drops(panel)
    assert set(drops["date"].dt.month) <= set(W.START_MONTHS)
    assert drops["drop_mm"].to_numpy() == pytest.approx(500.0)
    # Le mois mesuré par S1 est écarté comme départ (janvier) et comme arrivée (décembre)
    r00 = drops[(drops["reservoir_id"] == "R00") & (drops["season"] == 2019)]
    assert set(r00["date"].dt.month) == {11, 2, 3}


def test_empty_reservoir_is_censored():
    panel = make_panel(n_reservoirs=2, noise=0.0)
    panel.loc[(panel["reservoir_id"] == "R01") & (panel["date"] == "2021-02-01"), ["area_ha", "fill"]] = 0.0
    drops = W.monthly_drops(panel)
    january = drops[(drops["reservoir_id"] == "R01") & (drops["date"] == "2021-01-01")]
    assert january["censored"].all()
    assert not drops[drops["reservoir_id"] == "R00"]["censored"].any()


def test_peer_model_never_trains_on_the_scored_reservoir():
    drops = W.monthly_drops(make_panel())
    model = W.PeerModel(n_splits=4).fit(drops)
    assert set(model.fold_of_) == set(drops["reservoir_id"])
    # Une retenue inconnue reçoit la moyenne des modèles
    unknown = drops.head(3).assign(reservoir_id="NEW")
    each = np.column_stack([m.predict(unknown[W.FEATURES]) for m in model.models_])
    assert model.predict(unknown) == pytest.approx(each.mean(axis=1))


def test_inject_withdrawal_lowers_only_the_target_season():
    panel = make_panel(noise=0.0)
    injected = W.inject_withdrawal(panel, "R03", 2021, extra_mm=200.0)
    changed = (injected["area_ha"] != panel["area_ha"])
    dates = panel.loc[changed, "date"]
    assert (panel.loc[changed, "reservoir_id"] == "R03").all()
    assert dates.min() == pd.Timestamp("2021-11-01") and dates.max() <= pd.Timestamp("2022-06-01")
    drops = W.monthly_drops(injected)
    hit = drops[(drops["reservoir_id"] == "R03") & (drops["season"] == 2021)]
    assert hit["drop_mm"].to_numpy() == pytest.approx(700.0)


def test_episodic_flags_the_injected_season():
    panel = W.inject_withdrawal(make_panel(), "R03", 2021, extra_mm=400.0)
    _, _, seasons = W.detect(panel)
    top = seasons.iloc[0]
    assert (top["reservoir_id"], top["season"]) == ("R03", 2021)
    assert top["flag"]
    assert seasons["flag"].sum() <= 2


def test_chronic_flags_a_reservoir_that_always_drops_faster():
    panel = make_panel()
    for season in range(2019, 2024):
        panel = W.inject_withdrawal(panel, "R07", season, extra_mm=300.0)
    _, reservoirs, _ = W.detect(panel)
    assert reservoirs.iloc[0]["reservoir_id"] == "R07"
    assert reservoirs.iloc[0]["flag"]
    assert reservoirs["flag"].sum() == 1
