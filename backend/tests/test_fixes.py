"""Tests de non-régression des correctifs du backend."""
from __future__ import annotations

import numpy as np
import pytest
from fastapi import HTTPException
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder, StandardScaler

from app.config import settings
from app.deps import require_api_key
from app.services.llm import _strip_reasoning
from app.services.ml import PeriodsUntilDryService


def _service(model_name: str) -> PeriodsUntilDryService:
    """Service v2 construit en mémoire (sans fichiers), comme après ml/train.py."""
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 12))
    y = 5 + 3 * X[:, 0]
    svc = PeriodsUntilDryService.__new__(PeriodsUntilDryService)
    svc.scaler = StandardScaler().fit(X * 10 + 50)  # échelle très différente des données
    svc.model = RandomForestRegressor(n_estimators=20, random_state=0).fit(X, y)
    svc.le_saison = LabelEncoder().fit(["pluies", "seche"])
    svc.le_ville = None
    svc.features = None
    svc.metadata = {"model": model_name}
    return svc


def test_random_forest_receives_unscaled_input():
    """La RandomForest de ml/train.py est entraînée sans normalisation (bug D3)."""
    svc = _service("RandomForest")
    data = {"ndwi_moyen": 0.3, "saison": "seche"}
    expected = svc.model.predict(svc._to_vector(data))[0]
    assert svc.predict_periods_until_dry(data) == int(max(1, min(20, round(expected))))


def test_gradient_boosting_receives_scaled_input():
    svc = _service("GradientBoosting")
    assert svc._expects_scaled_input


def test_zero_ndwi_is_not_treated_as_missing():
    svc = _service("RandomForest")
    vec = svc._to_vector({"ndwi_moyen": 0.5, "ndwi_t1": 0.0})
    assert vec[0, 1] == 0.0          # ndwi_t1 = 0.0 conservé (et non remplacé par 0.5)
    assert vec[0, 4] == pytest.approx(0.5)


def test_season_is_encoded_from_label():
    svc = _service("RandomForest")
    assert svc._to_vector({"saison": "seche"})[0, 8] == 1.0
    assert svc._to_vector({"saison": "pluies"})[0, 8] == 0.0


def test_api_key_constant_time_comparison():
    settings.api_key = "secret-test-key"
    try:
        assert require_api_key("secret-test-key") == "secret-test-key"
        with pytest.raises(HTTPException):
            require_api_key("secret-test-kez")
        with pytest.raises(HTTPException):
            require_api_key(None)
    finally:
        settings.api_key = "change-me-in-production"


def test_recompute_endpoint_requires_api_key():
    from app.routes.water import recompute_all_scores
    import inspect

    params = inspect.signature(recompute_all_scores).parameters
    assert any(getattr(p.default, "dependency", None) is require_api_key for p in params.values())


def test_strip_reasoning_block():
    assert _strip_reasoning("<think>raisonnement</think>\n Agir vite.") == "Agir vite."
    assert _strip_reasoning("<think>seulement</think>") is None
    assert _strip_reasoning(None) is None
