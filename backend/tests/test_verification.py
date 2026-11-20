"""Tests de la vérification des prévisions émises (ml/verification.py)."""
from __future__ import annotations

import pandas as pd
import pytest

from ml import verification as V


def observed(values: dict[str, list[float]], start: str = "2024-10") -> pd.DataFrame:
    """Remplissage mensuel observé, une série par réservoir à partir de `start`."""
    frames = []
    for rid, fills in values.items():
        months = pd.date_range(start, periods=len(fills), freq="MS")
        frames.append(pd.DataFrame({"reservoir_id": rid, "month": months, "fill": fills}))
    return pd.concat(frames, ignore_index=True)


def forecast(rid, issue, horizon, target, pred, lo, hi, p, status, now=0.5):
    return {"reservoir_id": rid, "issue_month": issue, "horizon": horizon, "target_month": target,
            "fill_now": now, "fill_pred": pred, "fill_lo80": lo, "fill_hi80": hi,
            "p_critical": p, "status": status, "model_version": "3.0"}


def test_seasonal_normal_uses_previous_years_only():
    # Octobre : 0.8 (2024), 0.6 (2025), 0.4 (2026)
    obs = observed({"A": [0.8] + [0.5] * 11 + [0.6] + [0.5] * 11 + [0.4]})
    normal = V.seasonal_normal(obs).set_index("month")["normal"]
    assert pd.isna(normal[pd.Timestamp("2024-10-01")])
    assert normal[pd.Timestamp("2025-10-01")] == pytest.approx(0.8)
    assert normal[pd.Timestamp("2026-10-01")] == pytest.approx(0.7)       # médiane de 0.8 et 0.6


def test_match_keeps_only_measured_targets_and_scores_them():
    obs = observed({"A": [0.6] * 12 + [0.5, 0.1], "B": [0.6] * 12 + [0.5, float("nan")]})
    fc = pd.DataFrame([
        forecast("A", "2025-10-01", 1, "2025-11-01", 0.15, 0.05, 0.30, 0.8, "à risque"),   # juste, crise
        forecast("A", "2025-09-01", 2, "2025-11-01", 0.50, 0.40, 0.60, 0.1, "actif"),      # manquée
        forecast("B", "2025-10-01", 1, "2025-11-01", 0.40, 0.30, 0.50, 0.6, "à risque"),   # non mesurée
        forecast("A", "2025-11-01", 1, "2025-12-01", 0.10, 0.05, 0.20, 0.5, "à risque"),   # pas encore mesurée
    ])
    v = V.match(fc, obs, critical=0.20)
    assert len(v) == 2 and set(v["horizon"]) == {1, 2}
    s = V.scores(v)
    assert s["n"] == 2 and s["mae"] == pytest.approx((0.05 + 0.40) / 2)
    assert s["normal_mae"] == pytest.approx(0.5)                          # normale de novembre : 0.6
    assert s["skill_vs_normal"] == pytest.approx(1 - 0.225 / 0.5)
    assert s["coverage_80"] == pytest.approx(0.5)
    assert (s["events"], s["alerts"], s["hits"], s["false_alarms"]) == (2, 1, 1, 0)
    assert s["recall"] == pytest.approx(0.5) and s["precision"] == pytest.approx(1.0)
    assert (s["crisis_onsets"], s["onsets_detected"]) == (2, 1)
    assert s["brier"] == pytest.approx(((0.8 - 1) ** 2 + (0.1 - 1) ** 2) / 2)


def test_summarise_by_horizon_and_month_labels():
    obs = observed({"A": [0.6] * 12 + [0.5, 0.1]})
    fc = pd.DataFrame([forecast("A", "2025-10-01", 1, "2025-11-01", 0.15, 0.05, 0.30, 0.8, "à risque")])
    v = V.match(fc, obs, critical=0.20)
    assert V.summarise(v, "horizon")[0]["horizon"] == 1
    assert V.summarise(v, "target_month")[0]["target_month"] == "2025-11"


def test_scores_without_reference_year():
    obs = observed({"A": [0.5, 0.4]})                                    # première année : pas de normale
    fc = pd.DataFrame([forecast("A", "2024-10-01", 1, "2024-11-01", 0.45, 0.3, 0.6, 0.0, "actif")])
    s = V.scores(V.match(fc, obs, critical=0.20))
    assert s["normal_mae"] is None and s["skill_vs_normal"] is None and s["precision"] is None


def test_verification_report_window_and_groups(monkeypatch):
    from datetime import date

    from app.services import reservoirs as svc

    obs = observed({"A": [0.6] * 12 + [0.5, 0.1]})
    fc = pd.DataFrame([
        forecast("A", "2025-10-01", 1, "2025-11-01", 0.15, 0.05, 0.30, 0.8, "à risque"),
        forecast("A", "2025-09-01", 2, "2025-11-01", 0.50, 0.40, 0.60, 0.1, "actif"),
    ])
    seen = {}

    def frame(db, target_months=None, since=None):
        seen["since"] = since
        return V.match(fc, obs, critical=0.20)

    monkeypatch.setattr(svc, "latest_observed_month", lambda db: date(2025, 11, 1))
    monkeypatch.setattr(svc, "verification_frame", frame)
    report = svc.verification_report(db=None, months=12)
    assert seen["since"] == date(2024, 12, 1)
    assert report["window"] == {"from": "2024-12", "to": "2025-11"} and report["models"] == ["3.0"]
    assert report["overall"]["n"] == 2 and [r["horizon"] for r in report["by_horizon"]] == [1, 2]
    assert report["by_target_month"][0]["target_month"] == "2025-11"
