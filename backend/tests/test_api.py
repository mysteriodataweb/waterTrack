from __future__ import annotations

from pydantic import ValidationError
import pytest

from app.schemas import (
    PredictRequest,
    NavigationRouteRequest,
    RoutePoint,
)
from app.deps import require_api_key
from app.config import settings


def test_predict_request_valid():
    req = PredictRequest(ndwi_moyen=0.4)
    assert req.ndwi_moyen == 0.4


def test_predict_request_rejects_out_of_range():
    # Pydantic rejette NDWI hors [-1, 1] (validation des entrées rétablie).
    with pytest.raises(ValidationError):
        PredictRequest(ndwi_moyen=5.0)


def test_navigation_request_valid():
    req = NavigationRouteRequest(
        start=RoutePoint(lat=12.3, lng=-1.5),
        end=RoutePoint(lat=12.4, lng=-1.6),
        profile="foot-walking",
    )
    assert req.profile == "foot-walking"


def test_navigation_rejects_bad_profile():
    with pytest.raises(ValidationError):
        NavigationRouteRequest(
            start=RoutePoint(lat=12.3, lng=-1.5),
            end=RoutePoint(lat=12.4, lng=-1.6),
            profile="flying",  # profile non autorisé
        )


def test_wrong_api_key_rejected():
    settings.api_key = "secret-test-key"
    try:
        with pytest.raises(Exception):
            require_api_key("mauvaise-cle")
    finally:
        settings.api_key = "change-me-in-production"
