from __future__ import annotations

from app.services.ml import RuleBasedRiskService
from app.services.recommande import generer_recommandation, _regle_recommandation, _risque_niveau


def test_rule_based_risk_high_ndwi():
    svc = RuleBasedRiskService()
    res = svc.get_risk_score({"ndwi_moyen": 0.6})
    assert res["status"] == "actif"
    assert res["score"] <= 0.3


def test_rule_based_risk_low_ndwi():
    svc = RuleBasedRiskService()
    res = svc.get_risk_score({"ndwi_moyen": 0.05})
    assert res["status"] == "tari"


def test_rule_based_risk_missing():
    svc = RuleBasedRiskService()
    res = svc.get_risk_score({})
    assert res["status"] == "inconnu"


def test_risque_niveau():
    assert _risque_niveau({"ndwi_actuel": 0.1}) == "CRITIQUE"
    assert _risque_niveau({"ndwi_actuel": 0.3}) == "ÉLEVÉ"
    assert _risque_niveau({"ndwi_actuel": 0.5}) == "MODÉRÉ"
    assert _risque_niveau({"ndwi_actuel": 0.8}) == "FAIBLE"


def test_recommendation_fallback_deterministic():
    pred = {
        "ndwi_actuel": 0.1,
        "vitesse_degradation": "rapide",
        "date_tarissement": "2025-S1",
    }
    # Sans clé Groq via env, le fallback règle doit produire un texte stable.
    txt = _regle_recommandation(pred, "ong")
    assert "CRITIQUE" in txt
    assert "2025-S1" in txt


def test_generer_recommandation_never_empty():
    pred = {"ndwi_actuel": 0.5, "vitesse_degradation": "stable", "date_tarissement": None}
    txt = generer_recommandation(pred, "communaute")
    assert isinstance(txt, str) and len(txt) > 0
