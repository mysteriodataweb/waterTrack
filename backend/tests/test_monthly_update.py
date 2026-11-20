"""Tests de la mise à jour mensuelle : rattrapage, contrôles, téléchargement du paquet, ligne de commande.

Earth Engine, la base et le modèle sont remplacés par des doublures : on teste
l'enchaînement (ordre des mois, enregistrement mois par mois, émissions), pas la mesure.
"""
from __future__ import annotations

import hashlib
import io
from datetime import date

import numpy as np
import pandas as pd
import pytest

import app.collectors.monthly as M
import ml.forecasting as FC
from scripts import monthly_update as cli


# --------------------------------------------------------------------------- #
# Planification, retard, qualité
# --------------------------------------------------------------------------- #
def test_plan_months_catches_up_in_order():
    assert M.plan_months(date(2026, 8, 1), "2026-10") == (["2026-09", "2026-10"], 0)


def test_plan_months_defers_beyond_the_cap():
    months, deferred = M.plan_months(date(2026, 1, 1), "2026-10", max_months=3)
    assert months == ["2026-02", "2026-03", "2026-04"] and deferred == 6


def test_plan_months_up_to_date_and_empty_database():
    assert M.plan_months(date(2026, 10, 1), "2026-10") == ([], 0)
    with pytest.raises(RuntimeError, match="load_v3"):
        M.plan_months(None, "2026-10")


def test_freshness():
    today = date(2026, 11, 20)                       # dernier mois complet : octobre
    assert M.freshness(date(2026, 9, 1), today) == {"latest_month": "2026-09", "months_behind": 1, "data": "ok"}
    assert M.freshness(date(2026, 8, 1), today)["data"] == "ok"        # 2 mois : retard normal
    assert M.freshness(date(2026, 7, 1), today)["data"] == "stale"     # 3 mois : la collecte s'est arrêtée
    assert M.freshness(None, today) == {"latest_month": None, "months_behind": None, "data": "empty"}


def test_quality_warnings():
    good = pd.DataFrame({"area_source": ["S2"] * 9 + ["manquant"], "precip_mm": 1.0, "pet_mm": 1.0})
    assert M.quality_warnings(good, "2026-10") == []
    cloudy = good.assign(area_source=["S2"] * 5 + ["manquant"] * 5, precip_mm=np.nan, pet_mm=np.nan)
    warnings = M.quality_warnings(cloudy, "2026-10")
    assert len(warnings) == 2 and "50%" in warnings[0] and "forçages" in warnings[1]
    assert M.quality_warnings(good.iloc[:0], "2026-10") == ["2026-10 : aucune retenue mesurée"]


# --------------------------------------------------------------------------- #
# Rattrapage avec doublures
# --------------------------------------------------------------------------- #
class FakeSession:
    def __init__(self, log):
        self.log = log

    def commit(self):
        self.log.append("commit")

    def rollback(self):
        self.log.append("rollback")

    def close(self):
        self.log.append("close")


@pytest.fixture
def fake_world(monkeypatch):
    """Base contenant les mois jusqu'en août 2026 ; ERA5-Land et CHIRPS publiés jusqu'en octobre."""
    state = {"stored": {"2026-08"}, "log": [], "issued": [], "fail_on": None}

    def collect(month, regions, hybas, bundle):
        if month == state["fail_on"]:
            raise RuntimeError("Earth Engine : délai dépassé")
        state["log"].append(f"collect {month}")
        return pd.DataFrame({"reservoir_id": ["A", "B"], "month": month, "area_source": ["S2", "S1"],
                             "precip_mm": 0.0, "pet_mm": 400.0})

    def upsert(db, df):
        state["stored"].add(df["month"].iloc[0])
        return len(df)

    def publish(db, bundle, issue):
        state["issued"].append(issue)
        return {"issue_month": issue, "forecasts": 6, "sources_updated": 2, "status_counts": {"actif": 2}}

    monkeypatch.setattr(FC, "load_bundle", lambda: {"critical_fill": 0.20})
    monkeypatch.setattr(M, "EarthEngineClient", lambda: type("EE", (), {"initialize": lambda self: None})())
    monkeypatch.setattr(M, "SessionLocal", lambda: FakeSession(state["log"]))
    monkeypatch.setattr(M, "last_available_month", lambda: "2026-10")
    monkeypatch.setattr(M, "collect_month", collect)
    monkeypatch.setattr(M, "forecast_and_publish", publish)
    monkeypatch.setattr(M.svc, "latest_observed_month",
                        lambda db: pd.Period(max(state["stored"]), "M").to_timestamp().date())
    monkeypatch.setattr(M.svc, "month_observed", lambda db, month: month in state["stored"])
    monkeypatch.setattr(M.svc, "region_geojson", lambda db: {"A": {}, "B": {}})
    monkeypatch.setattr(M.svc, "modelable_hybas", lambda db: {"A": 1, "B": 1})
    monkeypatch.setattr(M.svc, "upsert_observations", upsert)
    return state


def test_catch_up_collects_every_missing_month_and_issues_each(fake_world):
    summary = M.run_monthly_update()
    assert [e for e in fake_world["log"] if e.startswith("collect")] == ["collect 2026-09", "collect 2026-10"]
    assert fake_world["issued"] == ["2026-09", "2026-10"]
    assert summary["collected"] == 4 and summary["latest_month"] == "2026-10"
    assert [m["month"] for m in summary["months"]] == ["2026-09", "2026-10"]
    assert summary["months"][0]["sources"] == {"S2": 1, "S1": 1}
    assert summary["issue_month"] == "2026-10" and summary["deferred_months"] == 0


def test_a_failed_month_keeps_the_previous_ones(fake_world):
    fake_world["fail_on"] = "2026-10"
    with pytest.raises(RuntimeError, match="délai"):
        M.run_monthly_update()
    assert "2026-09" in fake_world["stored"] and "2026-10" not in fake_world["stored"]
    log = fake_world["log"]
    assert log.index("commit") < log.index("rollback") and log[-1] == "close"
    assert fake_world["issued"] == []


def test_up_to_date_database_reissues_the_latest_month(fake_world):
    fake_world["stored"] |= {"2026-09", "2026-10"}
    summary = M.run_monthly_update()
    assert not any(e.startswith("collect") for e in fake_world["log"])
    assert fake_world["issued"] == ["2026-10"] and summary["months"] == []


def test_explicit_month_is_skipped_unless_forced(fake_world):
    M.run_monthly_update(month="2026-08")
    assert not any(e.startswith("collect") for e in fake_world["log"])
    M.run_monthly_update(month="2026-08", force=True)
    assert "collect 2026-08" in fake_world["log"]
    assert fake_world["issued"] == ["2026-08", "2026-08"]


# --------------------------------------------------------------------------- #
# Téléchargement du paquet de modèles
# --------------------------------------------------------------------------- #
PAYLOAD = b"paquet de modeles"
GOOD_SHA = hashlib.sha256(PAYLOAD).hexdigest()
URL = "https://example.org/bundle.joblib"


@pytest.fixture
def served(monkeypatch):
    calls = []

    def urlopen(url, timeout):
        calls.append(url)
        return io.BytesIO(PAYLOAD)

    monkeypatch.setattr(FC.urllib.request, "urlopen", urlopen)
    return calls


def test_fetch_bundle_checks_the_fingerprint(tmp_path, served):
    path = tmp_path / "bundle.joblib"
    FC.fetch_bundle(path, URL, GOOD_SHA)
    assert path.read_bytes() == PAYLOAD and served == [URL]


def test_fetch_bundle_refuses_a_wrong_or_missing_fingerprint(tmp_path, served):
    path = tmp_path / "bundle.joblib"
    with pytest.raises(RuntimeError, match="refusé"):
        FC.fetch_bundle(path, URL, "0" * 64)
    assert not path.exists() and not list(tmp_path.iterdir())
    with pytest.raises(RuntimeError, match="obligatoire"):
        FC.fetch_bundle(path, URL, "")
    with pytest.raises(RuntimeError, match="https"):
        FC.fetch_bundle(path, "http://example.org/bundle.joblib", GOOD_SHA)


def test_fetch_bundle_keeps_an_existing_file_and_needs_an_address(tmp_path, served, monkeypatch):
    path = tmp_path / "bundle.joblib"
    path.write_bytes(b"local")
    FC.fetch_bundle(path, URL, GOOD_SHA)
    monkeypatch.delenv(FC.BUNDLE_URL_ENV, raising=False)
    FC.fetch_bundle(tmp_path / "absent.joblib")
    assert path.read_bytes() == b"local" and served == []


# --------------------------------------------------------------------------- #
# Ligne de commande
# --------------------------------------------------------------------------- #
SUMMARY = {"issue_month": "2026-10", "forecasts": 288, "sources_updated": 65, "status_counts": {"actif": 90},
           "drying_forecasts": 0, "drying_note": "hors saison sèche", "collected": 96,
           "months": [{"month": "2026-10", "reservoirs": 96, "sources": {"S2": 95, "S1": 1}}],
           "deferred_months": 0, "warnings": [], "latest_month": "2026-10", "months_behind": 0, "data": "ok"}


def test_cli_success_writes_the_step_summary(monkeypatch, tmp_path):
    out = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(out))
    monkeypatch.setattr(cli, "run_monthly_update", lambda **kw: SUMMARY)
    assert cli.main([]) == cli.OK
    text = out.read_text(encoding="utf-8")
    assert "| 2026-10 | 96 | S1 1, S2 95 |" in text and "Dernier mois en base : **2026-10**" in text


def test_cli_exit_codes(monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(cli, "run_monthly_update", lambda **kw: {**SUMMARY, "data": "stale", "months_behind": 4})
    assert cli.main([]) == cli.STALE

    def boom(**kw):
        raise RuntimeError("base injoignable")

    monkeypatch.setattr(cli, "run_monthly_update", boom)
    assert cli.main(["--month", "2026-10"]) == cli.FAILED


def test_cli_passes_its_arguments(monkeypatch):
    seen = {}
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(cli, "run_monthly_update", lambda **kw: seen.update(kw) or SUMMARY)
    cli.main(["--month", "2026-09", "--force", "--max-months", "2"])
    assert seen == {"month": "2026-09", "force": True, "max_months": 2}


# --------------------------------------------------------------------------- #
# Contrôle de santé
# --------------------------------------------------------------------------- #
class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, statement):
        return None


def test_health_reports_stale_data_as_degraded(monkeypatch):
    from app.routes import health as H

    monkeypatch.setattr(H, "engine", type("Engine", (), {"connect": lambda self: FakeConnection()})())
    monkeypatch.setattr(H, "data_freshness",
                        lambda: {"latest_month": "2026-06", "months_behind": 4, "data": "stale"})
    out = H.health()
    assert out.status == "degraded" and out.database == "ok"
    assert out.data == "stale" and out.latest_month == "2026-06" and out.months_behind == 4

    monkeypatch.setattr(H, "data_freshness",
                        lambda: {"latest_month": "2026-10", "months_behind": 0, "data": "ok"})
    assert H.health().status == "ok"
