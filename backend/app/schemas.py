from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

Status = Literal["actif", "à risque", "tari", "inconnu"]
Profil = Literal["ong", "gouvernement", "agent_terrain", "communaute"]
Vitesse = Literal["rapide", "lente", "stable"]


# ---------- Requêtes ----------

class PredictRequest(BaseModel):
    ndwi_moyen: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    ndwi_t1: Optional[float] = None
    ndwi_t2: Optional[float] = None
    ndwi_t3: Optional[float] = None
    ndvi_moyen: Optional[float] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    saison: str = "seche"
    annee: int = date.today().year
    semestre: int = Field(default=1, ge=1, le=2)


class RoutePoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class NavigationRouteRequest(BaseModel):
    start: RoutePoint
    end: RoutePoint
    profile: Literal["driving-car", "foot-walking", "cycling-regular"] = "driving-car"


# ---------- Réponses ----------

class PredictResponse(BaseModel):
    score: float = Field(ge=0, le=1)
    status: Status
    periods_until_dry: Optional[int] = None
    source: Literal["ml", "règles"] = "ml"


class WaterSourceResponse(BaseModel):
    id: int
    longitude: float
    latitude: float
    zone: str
    zone_detail: Optional[str] = None
    superficie_km2: Optional[float] = None
    ndwi_moyen: Optional[float] = None
    risk_score: float
    status: Status
    date_analyse: Optional[date] = None
    geometry: Optional[dict] = None


class PaginatedSources(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[WaterSourceResponse]


class PeriodicPrediction(BaseModel):
    periode: str
    ndwi_predit: float
    ndwi_min: float
    ndwi_max: float
    probabilite_tarissement: float


class TarissementPrediction(BaseModel):
    water_source: int
    ndwi_actuel: float
    tendance: float
    vitesse_degradation: Vitesse
    date_tarissement: Optional[str] = None
    confiance: float
    probabilite_tarissement: float
    predictions: list[PeriodicPrediction]
    recommandation: Optional[str] = None
    recommandations: Optional[dict[str, str]] = None


class NavigationStep(BaseModel):
    instruction: str
    distance: float
    duration: float
    name: Optional[str] = None


class NavigationRouteResponse(BaseModel):
    profile: str
    distance: float
    duration: float
    geometry: list[list[float]]
    steps: list[NavigationStep]


class ReverseGeocodeResponse(BaseModel):
    label: str
    name: Optional[str] = None
    street: Optional[str] = None
    locality: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None


class AdminUpdateResponse(BaseModel):
    updated: int
    message: str


class PeriodRow(BaseModel):
    periode: str
    ndwi_moyen: float
    nb_sources: int


class ReportZoneRow(BaseModel):
    zone: str
    count: int


class ReportTopSourceRow(BaseModel):
    id: int
    zone_detail: Optional[str] = None
    status: Status
    risk_score: float
    ndwi_moyen: Optional[float] = None


class ReportSummary(BaseModel):
    periode: str
    date_generation: date
    total_sources: int
    statut: dict[str, int]
    superficie_totale_km2: float
    ndwi_moyen_global: Optional[float] = None
    nb_observations: int
    periodes: list[PeriodRow]
    zones: list[ReportZoneRow]
    top_risque: list[ReportTopSourceRow]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "error"]
    external: dict[str, Literal["ok", "error"]]
