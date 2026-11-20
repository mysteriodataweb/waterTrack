"""Tests des conseils pour agir construits sur les prévisions v3 (app/services/advice.py)."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from app.schemas import Advice
from app.services import advice as A

TODAY = date(2026, 11, 20)       # mesures d'octobre 2026 : un mois de retard, comme d'habitude


def forecast(fill_now: float, horizons: list[tuple], issue: str = "2026-10") -> dict:
    """horizons : (remplissage prévu, bas, haut, probabilité critique, statut) pour h = 1, 2, 3."""
    start = pd.Period(issue, "M")
    return {"issue_month": issue, "fill_now": fill_now, "critical_fill": 0.20, "horizons": [
        {"horizon": h, "target_month": str(start + h), "fill_pred": pred, "fill_lo80": lo, "fill_hi80": hi,
         "p_critical": p, "status": status}
        for h, (pred, lo, hi, p, status) in enumerate(horizons, start=1)]}


CALM = [(0.60, 0.50, 0.70, 0.02, "actif"), (0.55, 0.45, 0.65, 0.04, "actif"), (0.50, 0.40, 0.62, 0.08, "actif")]
DRYING = {"critical_month": "2027-03", "earliest_80": "2027-02", "latest_80": "2027-05",
          "usual_month": "2027-05", "lasts_to_june": False, "p_lasts_to_june": 0.10}

CASES = {
    "dry": (forecast(0.12, [(0.03, 0.0, 0.10, 0.97, "tari"), (0.01, 0.0, 0.08, 0.99, "tari"), (0.0, 0.0, 0.05, 0.99, "tari")]),
            None, "critique"),
    "below": (forecast(0.15, [(0.12, 0.05, 0.22, 0.85, "à risque"), (0.10, 0.03, 0.2, 0.9, "à risque"),
                              (0.08, 0.0, 0.2, 0.92, "à risque")]), None, "alerte"),
    "risk_next": (forecast(0.31, [(0.18, 0.10, 0.30, 0.62, "à risque"), (0.12, 0.05, 0.25, 0.80, "à risque"),
                                  (0.08, 0.0, 0.20, 0.90, "à risque")]), None, "alerte"),
    "refilling": (forecast(0.10, [(0.45, 0.20, 0.70, 0.15, "actif")] + CALM[1:], issue="2027-06"), None, "vigilance"),
    "risk_later": (forecast(0.40, [CALM[0], (0.25, 0.15, 0.35, 0.35, "actif"), (0.15, 0.05, 0.30, 0.66, "à risque")]),
                   None, "vigilance"),
    "watch": (forecast(0.40, [CALM[0], CALM[1], (0.30, 0.15, 0.45, 0.25, "actif")]), None, "vigilance"),
    "early_drying": (forecast(0.70, CALM), DRYING, "vigilance"),
    "ok": (forecast(0.70, CALM), {**DRYING, "critical_month": None, "earliest_80": None, "latest_80": None,
                                  "usual_month": None, "lasts_to_june": True, "p_lasts_to_june": 0.85}, "normal"),
}


@pytest.mark.parametrize("reason", CASES)
def test_each_situation_gets_its_level_and_actions(reason):
    fc, drying, level = CASES[reason]
    advice = A.build_advice(fc, drying, fill_change=-0.04, today=TODAY)
    assert (advice["reason"], advice["level"]) == (reason, level)
    assert set(advice["audiences"]) == set(A.AUDIENCES)
    for audience in advice["audiences"].values():
        assert audience["actions"] and all("{" not in s for s in audience["actions"])
        assert audience["text"].startswith(advice["headline"])
    Advice.model_validate({"reservoir_id": "R1", "issue_month": fc["issue_month"], **advice})


def test_level_matches_the_map_status_of_next_month():
    for reason, (fc, drying, level) in CASES.items():
        status = fc["horizons"][0]["status"]
        expected = {"tari": "critique", "à risque": "alerte"}.get(status)
        assert expected is None or level == expected, reason
        assert status != "actif" or level in ("normal", "vigilance"), reason


def test_messages_repeat_the_forecast_numbers():
    fc, _, _ = CASES["risk_next"]
    advice = A.build_advice(fc, None, fill_change=-0.04, today=TODAY)
    assert advice["headline"] == "Risque élevé (62 %) de passer sous le seuil critique de 20 % en novembre 2026."
    assert advice["situation"][0] == ("Remplissage mesuré en octobre 2026 : 31 % de la surface de référence "
                                      "(−4 points en un mois).")
    assert "18 % (8 fois sur 10 entre 10 % et 30 %)" in advice["situation"][1]


def test_later_risk_shows_the_month_it_is_expected():
    fc, _, _ = CASES["risk_later"]
    advice = A.build_advice(fc, None, today=TODAY)
    assert advice["deadline_month"] == "2027-01" and "janvier 2027" in advice["headline"]
    assert advice["when"] == "avant janvier 2027"
    assert len(advice["situation"]) == 3                     # mesure, mois prochain, mois du risque
    assert "Quand : avant janvier 2027." in advice["audiences"]["agent_terrain"]["text"]


def test_deadline_is_relative_to_today_because_data_lag():
    assert A.when_label("2026-11", TODAY) == "dès maintenant"
    assert A.when_label("2026-12", TODAY) == "dans les semaines qui viennent"
    assert A.when_label("2027-02", TODAY) == "avant février 2027"
    fc, _, _ = CASES["risk_next"]
    assert A.build_advice(fc, None, today=date(2026, 10, 5))["when"] == "dans les semaines qui viennent"
    assert A.build_advice(fc, None, today=TODAY)["when"] == "dès maintenant"


def test_no_deadline_without_alert():
    for reason in ("watch", "refilling", "ok"):
        fc, drying, _ = CASES[reason]
        assert A.build_advice(fc, drying, today=TODAY)["when"] is None


def test_dry_season_line():
    advice = A.build_advice(*CASES["early_drying"][:2], today=TODAY)
    assert "plus tôt que d'habitude (mai 2027)" in advice["headline"]
    assert advice["situation"][-1] == ("Saison sèche : passage sous le seuil le plus probable en mars 2027 "
                                       "(8 fois sur 10 entre février 2027 et mai 2027) ; d'habitude : mai 2027.")
    lasts = A.build_advice(*CASES["ok"][:2], today=TODAY)
    assert lasts["situation"][-1] == "Saison sèche : devrait tenir jusqu'au retour des pluies, fin juin (85 % de chances)."


def test_caveats():
    fc, _, _ = CASES["refilling"]
    advice = A.build_advice(fc, None, today=TODAY, data_stale=True, to_validate=True)
    text = " ".join(advice["caveats"])
    assert "Dernières mesures : juin 2027" in text
    assert "fourchette est large (20 % à 70 %)" in text
    assert "pas encore confirmé sur le terrain" in text
    assert advice["caveats"][-1].startswith("Surface en eau mesurée par satellite")
    assert len(A.build_advice(*CASES["ok"][:2], today=TODAY)["caveats"]) == 1


def test_flood_adds_safety_actions():
    advice = A.build_advice(forecast(1.20, CALM, issue="2026-08"), None, today=date(2026, 9, 15))
    assert "déborde la surface de référence" in advice["situation"][0]
    assert any("digue" in s for s in advice["audiences"]["agent_terrain"]["actions"])
    assert not any("digue" in s for s in advice["audiences"]["ong"]["actions"])


def test_every_reason_has_actions_for_every_audience():
    for reason, action_set in A.ACTION_SET.items():
        assert set(A.ACTIONS[action_set]) == set(A.AUDIENCES), reason


# --------------------------------------------------------------------------- #
# API et bulletin
# --------------------------------------------------------------------------- #
def test_advice_route(monkeypatch):
    from app.routes import reservoirs as route
    from app.services import reservoirs as svc

    fc, _, _ = CASES["risk_next"]
    payload = {**fc, "reservoir_id": "R1", "source_id": None, "model_version": "3.0 (test)"}

    class FakeDB:
        def get(self, model, key):
            return SimpleNamespace(validation="a_valider") if key == "R1" else None

    monkeypatch.setattr(route, "_forecast_payload", lambda db, rid: payload)
    monkeypatch.setattr(svc, "drying_forecasts", lambda db, issue: {})
    monkeypatch.setattr(svc, "fill_change", lambda db, rid, issue: -0.04)
    monkeypatch.setattr(svc, "latest_observed_month", lambda db: date(2026, 10, 1))
    body = Advice.model_validate(route.reservoir_advice("R1", db=FakeDB()))
    assert body.level == "alerte" and body.model_version == "3.0 (test)"
    assert any("pas encore confirmé" in c for c in body.caveats)
    with pytest.raises(route.HTTPException) as exc:
        route.reservoir_advice("inconnu", db=FakeDB())
    assert exc.value.status_code == 404


def test_bulletin_rows_carry_level_and_message(monkeypatch):
    from app.services import reservoirs as svc

    rows = []
    for rid, (fc, _, _) in (("R1", CASES["risk_next"]), ("R2", CASES["watch"])):
        for h in fc["horizons"]:
            rows.append({"reservoir_id": rid, "issue_month": date(2026, 10, 1), "horizon": h["horizon"],
                         "target_month": pd.Period(h["target_month"], "M").to_timestamp().date(),
                         "fill_now": fc["fill_now"], "fill_pred": h["fill_pred"], "fill_lo80": h["fill_lo80"],
                         "fill_hi80": h["fill_hi80"], "p_critical": h["p_critical"], "status": h["status"],
                         "model_version": "3.0"})
    results = iter([
        [("R1", date(2026, 10, 1), 0.31, 3.1, None, "S2"), ("R2", date(2026, 10, 1), 0.40, 4.0, None, "S2")],
        [("R1", "application", 10.0, "valide", 12.3, -1.5), ("R2", "JRC", 10.0, "a_valider", 12.4, -1.6)],
        [("R1", 7)],
    ])

    class FakeDB:
        def execute(self, query):
            return SimpleNamespace(all=lambda: next(results))

    monkeypatch.setattr(svc, "forecasts_frame", lambda db, issue=None: pd.DataFrame(rows))
    monkeypatch.setattr(svc, "drying_forecasts", lambda db, issue: {})
    bulletin = svc.build_bulletin(FakeDB())
    by_id = {r["reservoir_id"]: r for r in bulletin["reservoirs"]}
    assert (by_id["R1"]["level"], by_id["R2"]["level"]) == ("alerte", "vigilance")
    assert by_id["R1"]["message"].startswith("Risque élevé (62")
    assert "level,message" in svc.bulletin_to_csv(bulletin).splitlines()[0]
