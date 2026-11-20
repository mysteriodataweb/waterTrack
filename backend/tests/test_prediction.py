from __future__ import annotations

from app.services.ml import RuleBasedRiskService


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
