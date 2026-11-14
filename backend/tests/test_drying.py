"""Tests du modèle de mois d'assèchement (ml/drying.py) sur un panel synthétique."""
import numpy as np
import pandas as pd
import pytest

import ml.drying as D


def make_panel(curves: dict[str, list[float]], start: str = "2019-07") -> pd.DataFrame:
    """Panel mensuel : une série de remplissage par réservoir, à partir de `start`."""
    frames = []
    for rid, fill in curves.items():
        dates = pd.date_range(start, periods=len(fill), freq="MS")
        frames.append(pd.DataFrame({
            "reservoir_id": rid, "date": dates, "fill": fill, "a_ref_ha": 20.0,
            "precip_mm": np.where(dates.month.isin([6, 7, 8, 9]), 150.0, 0.0), "pet_mm": 350.0,
        }))
    return pd.concat(frames, ignore_index=True)


# Saison type : juillet → juin, passage sous 0,20 en février (pas 4)
SEASON = [0.6, 0.9, 1.0, 0.9, 0.8, 0.6, 0.4, 0.15, 0.05, 0.0, 0.0, 0.3]


def test_step_and_season():
    dates = pd.Series(pd.to_datetime(["2020-07-01", "2020-10-01", "2021-01-01", "2021-06-01"]))
    assert D.season_of(dates).tolist() == [2020, 2020, 2020, 2020]
    assert D.step_of(dates.dt.month).tolist() == [-3, 0, 3, 8]


def test_crossing_step_and_survive():
    p = D.prepare(make_panel({"A": SEASON, "B": [1.0] * 12}))
    crossings = D.crossing_steps(D.season_curves(p))
    assert crossings.loc[("A", 2019)] == 4          # février
    assert crossings.loc[("B", 2019)] == D.SURVIVE  # ne franchit jamais


def test_issue_rows_event_and_window():
    p = D.prepare(make_panel({"A": SEASON * 3}))
    rows = D.issue_rows(p, ref_seasons=[2019, 2020, 2021])
    october = rows[(rows["season"] == 2020) & (rows["issue_step"] == 0)].iloc[0]
    assert october["K"] == 8 and october["event_k"] == 4
    # Déjà sous le seuil en février : aucune ligne émise ce mois-là
    assert not ((rows["issue_step"] == 4) & (rows["season"] == 2020)).any()


def test_features_do_not_use_the_future():
    base = make_panel({"A": SEASON * 3})
    changed = base.copy()
    changed.loc[changed["date"] > "2020-11-01", "fill"] = 0.99   # le futur change complètement
    r1 = D.issue_rows(D.prepare(base), ref_seasons=[2019], only_complete=False)
    r2 = D.issue_rows(D.prepare(changed), ref_seasons=[2019], only_complete=False)
    key = (r1["season"] == 2020) & (r1["issue_step"] == 1)
    cols = [c for c in D.ROW_FEATURES if not c.startswith("clim") and c != "anom_issue"]
    pd.testing.assert_frame_equal(r1.loc[key, cols].reset_index(drop=True),
                                  r2.loc[(r2["season"] == 2020) & (r2["issue_step"] == 1), cols].reset_index(drop=True))


def test_leave_one_season_out_climatology():
    s2 = list(SEASON)
    s2[6] = 0.1    # janvier de la 2e saison très bas : franchit dès janvier (pas 3)
    p = D.prepare(make_panel({"A": SEASON + s2 + SEASON}))
    rows = D.issue_rows(p, ref_seasons=[2019, 2020, 2021])
    clim = rows.groupby("season")["clim_cross"].first()
    # la saison 2020 ne voit que 2019 et 2021 (pas 4) ; les autres voient la médiane avec 2020
    assert clim.loc[2020] == 4
    assert clim.loc[2019] == pytest.approx(3.5)


def test_survival_distribution_sums_to_one():
    p = D.prepare(make_panel({"A": SEASON * 3, "B": [1.0] * 36}))
    rows = D.issue_rows(p, ref_seasons=[2019, 2020, 2021])

    class Constant:
        def predict_proba(self, X):
            return np.column_stack([np.full(len(X), 0.7), np.full(len(X), 0.3)])

    dist = D.predict_distribution(Constant(), rows)
    assert np.allclose(dist.sum(axis=1), 1)
    q = D.summarise(dist, rows)
    assert (q["k_q50"] <= rows["K"] + 1).all()
    assert D.distribution_metrics(dist, rows)["coverage_80"] <= 1


def bulletin_panel() -> pd.DataFrame:
    """30 retenues, 6 saisons : 15 franchissent le seuil en février, 15 tiennent jusqu'aux pluies."""
    lasting = [0.9, 1.0, 1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.7]
    curves = {f"D{i:02d}": SEASON * 6 for i in range(15)} | {f"L{i:02d}": lasting * 6 for i in range(15)}
    return make_panel(curves)


def test_issue_bulletin_trains_on_past_seasons_only(monkeypatch):
    monkeypatch.setattr(D, "MIN_TRAIN_ROWS", 50)
    panel = bulletin_panel()
    out = D.issue_bulletin(panel, "2023-11").set_index("reservoir_id")
    assert list(out.columns) == D.BULLETIN_COLUMNS[1:]
    assert len(out) == 30 and (out["issue_month"] == "2023-11").all()
    assert (out.loc[out.index.str.startswith("D"), "critical_month"] == "2024-02").all()
    assert (out.loc[out.index.str.startswith("L"), "critical_month"] == D.AFTER_JUNE).all()
    assert out.loc["L00", "p_lasts_to_june"] > 0.9 > 0.1 > out.loc["D00", "p_lasts_to_june"]
    # Ce qui se passe après le mois d'émission ne change pas le bulletin
    changed = panel.copy()
    changed.loc[changed["date"] > "2023-11-01", "fill"] = 0.99
    pd.testing.assert_frame_equal(D.issue_bulletin(changed, "2023-11"), D.issue_bulletin(panel, "2023-11"))


def test_issue_bulletin_rejects_wet_season_and_short_history():
    panel = bulletin_panel()
    with pytest.raises(ValueError, match="hors saison sèche"):
        D.issue_bulletin(panel, "2023-08")
    with pytest.raises(ValueError, match="historique insuffisant"):
        D.issue_bulletin(panel, "2019-11")


def test_forecast_drying_is_empty_when_everything_is_already_critical(monkeypatch):
    monkeypatch.setattr(D, "MIN_TRAIN_ROWS", 50)
    panel = bulletin_panel()
    panel.loc[panel["date"] == "2023-11-01", "fill"] = 0.05
    out = D.issue_bulletin(panel, "2023-11")
    assert out.empty and list(out.columns) == D.BULLETIN_COLUMNS
