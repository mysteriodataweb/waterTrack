from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..schemas import (
    NavigationRouteRequest,
    NavigationRouteResponse,
    NavigationStep,
    ReverseGeocodeResponse,
)

router = APIRouter()

_ALLOWED_PROFILES = {"driving-car", "foot-walking", "cycling-regular"}


def _require_ors_key():
    if not settings.openroute_api_key:
        raise HTTPException(status_code=503, detail="OPENROUTE_API_KEY manquant dans .env")
    return settings.openroute_api_key


@router.post("/navigation/route", response_model=NavigationRouteResponse)
def get_navigation_route(payload: NavigationRouteRequest):
    key = _require_ors_key()
    profile = payload.profile if payload.profile in _ALLOWED_PROFILES else "driving-car"

    url = f"https://api.openrouteservice.org/v2/directions/{profile}/geojson"
    body = json.dumps({
        "coordinates": [[payload.start.lng, payload.start.lat], [payload.end.lng, payload.end.lat]],
        "instructions": True,
        "language": "fr",
    }).encode("utf-8")

    req = urllib.request.Request(
        url, data=body, method="POST",
        # L'endpoint `/geojson` exige le header Accept `application/geo+json`
        # (sinon ORS renvoie une erreur 406 "This response format is not supported").
        headers={"Authorization": key, "Content-Type": "application/json", "Accept": "application/geo+json,application/geo+json;charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise HTTPException(status_code=exc.code, detail=exc.read().decode("utf-8", errors="ignore")) from exc
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=503, detail=f"OpenRouteService indisponible: {exc.reason}") from exc

    feature = (data.get("features") or [None])[0]
    if not feature:
        raise HTTPException(status_code=502, detail="Aucun itinéraire retourné")

    props = feature.get("properties") or {}
    summary = props.get("summary") or {}
    steps = []
    for seg in props.get("segments") or []:
        for step in seg.get("steps") or []:
            steps.append(NavigationStep(
                instruction=step.get("instruction", "Continuer"),
                distance=step.get("distance", 0),
                duration=step.get("duration", 0),
                name=step.get("name"),
            ))
    return NavigationRouteResponse(
        profile=profile,
        distance=summary.get("distance", 0),
        duration=summary.get("duration", 0),
        geometry=(feature.get("geometry") or {}).get("coordinates", []),
        steps=steps,
    )


def _coord_label(lat: float, lng: float) -> str:
    return f"{lat:.4f}, {lng:.4f}"


def _reverse_via_ors(lat: float, lng: float) -> ReverseGeocodeResponse | None:
    """Géocodage inverse ORS. Retourne None si indisponible (quota, 403...)."""
    if not settings.openroute_api_key:
        return None
    key = settings.openroute_api_key
    query = urllib.parse.urlencode({"api_key": key, "point.lon": lng, "point.lat": lat, "size": 1, "lang": "fr"})
    req = urllib.request.Request(
        f"https://api.openrouteservice.org/geocode/reverse?{query}", method="GET",
        headers={"Authorization": key, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError:
        # Quota épuisé (403 "Quota exceeded"), rate limit ou réseau : on bascule.
        return None

    features = data.get("features") or []
    if not features:
        return None
    props = features[0].get("properties") or {}
    label = props.get("label") or props.get("name")
    if not label:
        return None
    return ReverseGeocodeResponse(
        label=label,
        name=props.get("name"),
        street=props.get("street"),
        locality=props.get("locality") or props.get("county"),
        region=props.get("region"),
        country=props.get("country"),
    )


def _reverse_via_nominatim(lat: float, lng: float) -> ReverseGeocodeResponse | None:
    """Repli OpenStreetMap Nominatim : gratuit et sans clé API."""
    query = urllib.parse.urlencode({
        "format": "jsonv2", "lat": lat, "lon": lng, "zoom": 16,
        "addressdetails": 1, "accept-language": "fr",
    })
    req = urllib.request.Request(
        f"https://nominatim.openstreetmap.org/reverse?{query}", method="GET",
        # Nominatim exige un User-Agent identifiant l'application.
        headers={"User-Agent": "WaterTracker/2.0 (contact: watertracker@example.org)",
                 "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError:
        return None

    label = data.get("display_name")
    if not label:
        return None
    address = data.get("address") or {}
    return ReverseGeocodeResponse(
        label=label,
        name=data.get("name") or address.get("village") or address.get("town"),
        street=address.get("road"),
        locality=address.get("village") or address.get("town") or address.get("city") or address.get("county"),
        region=address.get("state"),
        country=address.get("country"),
    )


@router.get("/navigation/reverse", response_model=ReverseGeocodeResponse)
def get_reverse_geocode(lat: float, lng: float):
    """Nom du lieu à partir de coordonnées.

    C'est un libellé de confort : il ne doit JAMAIS faire échouer la navigation.
    On tente ORS, puis Nominatim, et en dernier recours on renvoie les
    coordonnées formatées avec un code 200.
    """
    for provider in (_reverse_via_ors, _reverse_via_nominatim):
        result = provider(lat, lng)
        if result is not None:
            return result
    return ReverseGeocodeResponse(label=_coord_label(lat, lng))
