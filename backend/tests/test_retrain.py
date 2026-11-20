"""Tests du réentraînement annuel avec contrôle avant mise en service (ml/retrain.py, scripts/retrain.py).

Panel synthétique (6 réservoirs, 6 ans) et champion aux estimateurs réduits : on teste
la mécanique (fenêtre, absence de fuite, décision, paquet utilisable par l'API), pas la qualité.
"""
from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

import ml.features as F
from ml import retrain as R
from ml.forecasting import forecast
from scripts import retrain as cli


def synthetic_panel(n_res: int = 6, start: str = "2019-01", months: int = 72, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, periods=months, freq="MS")
    season = np.sin(2 * np.pi * (dates.month.values - 5) / 12)
    frames = []
    for i in range(n_res):
        fill = np.clip(0.5 + 0.45 * season + 0.05 * i + rng.normal(0, 0.05, months), 0, 1.5)
        frames.append(pd.DataFrame({
            "reservoir_id": f"R{i}", "date": dates, "fill": fill, "area_source": "S2",
            "precip_mm": np.maximum(0, 150 * season + rng.normal(0, 10, months)),
            "pet_mm": 350 - 50 * season, "aet_mm": 40 + 20 * season, "t2m_c": 29 - 2 * season, "soil_moist": 0.2 + 0.1 * season,
        }))
    return pd.concat(frames, ignore_index=True)


def small_champion(panel: pd.DataFrame) -> dict:
    ids = sorted(panel["reservoir_id"].unique())
    rng = np.random.default_rng(1)
    static = pd.DataFrame(rng.normal(1, 0.3, (len(ids), len(F.STATIC_COLS))), index=ids, columns=list(F.STATIC_COLS))

    def h_models():
        quantile = lambda a: Pipeline([("model", HistGradientBoostingRegressor(
            loss="quantile", quantile=a, max_iter=40, max_leaf_nodes=7, min_samples_leaf=10, random_state=0))])
        return {"median": Pipeline([("impute", SimpleImputer(strategy="median")),
                                    ("model", RandomForestRegressor(n_estimators=20, min_samples_leaf=5, random_state=0))]),
                "target_mode": "level", "q_lo": quantile(0.10), "q_hi": quantile(0.90),
                "classifier": HistGradientBoostingClassifier(max_iter=40, max_leaf_nodes=7, random_state=0),
                "calibrator": None, "alert_threshold": 0.5}

    return {"version": "3.0", "created": "2026-01-01T00:00:00", "features": F.FEATURES, "horizons": [1, 2, 3],
            "critical_fill": 0.20, "static": static, "models": {h: h_models() for h in (1, 2, 3)}}


@pytest.fixture(scope="module")
def run():
    panel = synthetic_panel()
    champion = small_champion(panel)
    return panel, champion, R.retrain(panel, champion)


def test_window_is_the_latest_season(run):
    panel, _, result = run
    assert result.window == ("2024-01", "2024-12")
    targets = pd.to_datetime(result.forecasts["target_month"])
    assert targets.min() == pd.Timestamp("2024-01-01") and targets.max() == pd.Timestamp("2024-12-01")
    assert set(result.challenger) == {1, 2, 3} and all(s["n"] > 0 for s in result.challenger.values())


def test_candidate_bundle_is_served_by_the_api_inference(run):
    panel, champion, result = run
    bundle = result.bundle
    assert bundle["data_end"] == "2024-12" and bundle["retrained_from"] == "3.0 (2026-01-01T00:00:00)"
    assert bundle["static"] is champion["static"] and bundle["created"] != champion["created"]
    assert all(m["conformal_q"] >= 0 for m in bundle["models"].values())
    fc = forecast(bundle, panel)
    assert len(fc) == 3 * panel["reservoir_id"].nunique() and fc["fill_pred"].between(0, 1.5).all()
    assert json.dumps(bundle["retraining"], default=str)      # fiche du modèle sérialisable


def test_challenger_does_not_see_the_evaluation_window(run):
    panel, champion, result = run
    changed = panel.copy()
    late = changed["date"] >= "2024-07-01"
    changed.loc[late, "fill"] = 1.4 - changed.loc[late, "fill"]          # second semestre méconnaissable
    other = R.retrain(changed, champion)
    key = ["reservoir_id", "issue_month", "horizon"]
    early = lambda r: r.forecasts[r.forecasts["issue_month"] < "2024-07-01"].sort_values(key).reset_index(drop=True)
    pd.testing.assert_series_equal(early(result)["fill_pred"], early(other)["fill_pred"])


def test_decision_follows_the_checks(run):
    *_, result = run
    assert result.decision == ("promote" if all(c["passed"] for c in result.checks) else "keep")
    assert all(isinstance(c["passed"], bool) for c in result.checks)


def test_gate_rules():
    good = {"skill_vs_normal": 0.15, "coverage_80": 0.82}
    s = {1: good, 2: {**good, "skill_vs_normal": -0.03}, 3: {**good, "skill_vs_normal": -0.03}}
    assert all(c["passed"] for c in R.gate(s, {}, {}, {}))
    assert not R.gate({1: {**good, "skill_vs_normal": 0.0}}, {}, {}, {})[0]["passed"]       # pas mieux que la normale
    assert not R.gate({2: {**good, "skill_vs_normal": -0.08}}, {}, {}, {})[0]["passed"]      # trop loin derrière
    assert not R.gate({1: {**good, "coverage_80": 0.95}}, {}, {}, {})[1]["passed"]           # intervalle trop large


def test_gate_compares_with_the_champion_record_only_when_it_is_large_enough():
    s = {1: {"skill_vs_normal": 0.15, "coverage_80": 0.82}}
    few = R.gate(s, {1: {"n": R.MIN_CHAMPION_ROWS - 1}}, {1: 0.10}, {1: 0.20})
    assert len(few) == 2
    worse = R.gate(s, {1: {"n": R.MIN_CHAMPION_ROWS}}, {1: 0.10}, {1: 0.11})
    assert worse[-1]["value"] == pytest.approx(0.10) and not worse[-1]["passed"]
    close = R.gate(s, {1: {"n": R.MIN_CHAMPION_ROWS}}, {1: 0.10}, {1: 0.101})
    assert close[-1]["passed"]


def test_a_much_better_champion_record_keeps_the_champion(run):
    panel, champion, result = run
    record = result.forecasts.assign(abs_err=0.001)                         # champion presque parfait
    record = pd.concat([record] * 20, ignore_index=True)                     # bilan assez fourni
    kept = R.retrain(panel, champion, champion_record=record)
    assert kept.decision == "keep" and any("champion" in c["check"] and not c["passed"] for c in kept.checks)


def test_cli_writes_the_candidate_and_reports(tmp_path, monkeypatch, run):
    panel, champion, _ = run
    panel.to_parquet(tmp_path / "panel.parquet")
    joblib.dump(champion, tmp_path / "champion.joblib")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    out = tmp_path / "run"
    code = cli.main(["--panel", str(tmp_path / "panel.parquet"), "--bundle", str(tmp_path / "champion.joblib"),
                     "--out", str(out)])
    card = json.loads((out / "model_card.json").read_text(encoding="utf-8"))
    assert code == (cli.PROMOTE if card["decision"] == "promote" else cli.KEEP)
    assert joblib.load(out / "bundle.joblib")["data_end"] == "2024-12" and len(card["sha256"]) == 64
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "Fenêtre d'évaluation (mois cibles) : 2024-01 à 2024-12" in report and "| 1 mois |" in report
