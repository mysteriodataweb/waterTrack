from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint,
)
from geoalchemy2 import Geometry
from sqlalchemy.orm import relationship

from .database import Base


class WaterSource(Base):
    """Une source d'eau surveillée. La géométrie stocke sa localisation réelle."""

    __tablename__ = "water_sources"

    id          = Column(Integer, primary_key=True, index=True)
    geometry    = Column(Geometry("GEOMETRY", srid=4326), nullable=False)

    # Identifiant GPS stable (clé de liaison avec l'historique)
    gps_key     = Column(String, unique=True, index=True, nullable=True)
    longitude   = Column(Float, nullable=False)
    latitude    = Column(Float, nullable=False)
    zone        = Column(String, default="Ouagadougou")
    # Zone précise (province/commune dérivée du géocodage inverse : "kadiogo", "oubritenga"...).
    zone_detail = Column(String, default="Ouagadougou", nullable=True)
    superficie_km2 = Column(Float, nullable=True)

    ndwi_moyen  = Column(Float, nullable=True)
    risk_score  = Column(Float, default=0.0)
    status      = Column(String, default="actif")
    date_analyse = Column(Date, nullable=True)

    created_at  = Column(DateTime, default=datetime.utcnow)

    observations = relationship(
        "NdwiObservation",
        back_populates="source",
        cascade="all, delete-orphan",
    )


class NdwiObservation(Base):
    """Série temporelle de mesures NDWI/NDVI pour une source (cœur du temps réel)."""

    __tablename__ = "ndwi_observations"
    __table_args__ = (
        UniqueConstraint("source_id", "periode", name="uq_source_periode"),
        Index("ix_ndwi_source_date", "source_id", "observation_date"),
    )

    id              = Column(Integer, primary_key=True, index=True)
    source_id       = Column(Integer, ForeignKey("water_sources.id"), nullable=False)
    periode         = Column(String, nullable=False)          # ex: "2024-S1"
    observation_date = Column(Date, nullable=False)
    saison          = Column(String, nullable=True)
    ndwi            = Column(Float, nullable=False)
    ndvi            = Column(Float, nullable=True)
    evi             = Column(Float, nullable=True)
    precipitation   = Column(Float, nullable=True)
    temperature     = Column(Float, nullable=True)
    altitude        = Column(Float, nullable=True)
    humidite_sol    = Column(Float, nullable=True)
    satellite       = Column(String, nullable=True)           # sentinel-2, landsat...
    cloud_cover     = Column(Float, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    source = relationship("WaterSource", back_populates="observations")


# --------------------------------------------------------------------------- #
# Modèle v3 : surface en eau mensuelle et prévision du taux de remplissage
# --------------------------------------------------------------------------- #
class Reservoir(Base):
    """Plan d'eau physique. Plusieurs sources de l'application peuvent partager le même réservoir."""

    __tablename__ = "reservoirs"

    id          = Column(String, primary_key=True)                   # "R05" (application) ou "J12" (ajout JRC)
    origin      = Column(String, nullable=False)                      # "application" | "JRC"
    geometry    = Column(Geometry("GEOMETRY", srid=4326), nullable=False)  # plan d'eau
    region      = Column(Geometry("GEOMETRY", srid=4326), nullable=False)  # zone d'analyse satellite
    region_type = Column(String, nullable=True)
    hybas_id    = Column(BigInteger, nullable=True)                   # sous-bassin HydroBASINS niveau 10
    a_ref_ha    = Column(Float, nullable=True)                        # surface de référence (P95 entraînement)
    modelable   = Column(Boolean, default=False, nullable=False)
    # Validation de l'inventaire par le gestionnaire : "a_valider" | "valide" | "rejete"
    validation  = Column(String, default="a_valider", nullable=False)
    validation_note = Column(String, nullable=True)
    validated_at = Column(DateTime, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)

    sources = relationship("ReservoirSource", back_populates="reservoir", cascade="all, delete-orphan")


class ReservoirSource(Base):
    """Lien source de l'application <-> réservoir physique."""

    __tablename__ = "reservoir_sources"

    reservoir_id = Column(String, ForeignKey("reservoirs.id", ondelete="CASCADE"), primary_key=True)
    source_id    = Column(Integer, ForeignKey("water_sources.id", ondelete="CASCADE"), primary_key=True, unique=True)

    reservoir = relationship("Reservoir", back_populates="sources")


class WaterAreaObservation(Base):
    """Surface en eau mensuelle d'un réservoir (Sentinel-2 10 m, comblée par Sentinel-1) + forçages."""

    __tablename__ = "water_area_observations"
    __table_args__ = (UniqueConstraint("reservoir_id", "month", name="uq_area_reservoir_month"),)

    id           = Column(Integer, primary_key=True)
    reservoir_id = Column(String, ForeignKey("reservoirs.id", ondelete="CASCADE"), nullable=False, index=True)
    month        = Column(Date, nullable=False, index=True)           # 1er jour du mois
    area_ha      = Column(Float, nullable=True)
    fill         = Column(Float, nullable=True)                       # area / a_ref
    area_source  = Column(String, nullable=False)                     # S2 | S1 | interp | manquant
    valid_frac   = Column(Float, nullable=True)                       # part de pixels optiques non nuageux
    volume_m3    = Column(Float, nullable=True)                       # indicatif (Liebe et al. 2005)
    precip_mm    = Column(Float, nullable=True)
    pet_mm       = Column(Float, nullable=True)
    aet_mm       = Column(Float, nullable=True)
    t2m_c        = Column(Float, nullable=True)
    soil_moist   = Column(Float, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)


class FillForecast(Base):
    """Prévision du taux de remplissage émise à la fin d'un mois, pour un horizon de h mois."""

    __tablename__ = "fill_forecasts"
    __table_args__ = (UniqueConstraint("reservoir_id", "issue_month", "horizon", name="uq_forecast"),)

    id            = Column(Integer, primary_key=True)
    reservoir_id  = Column(String, ForeignKey("reservoirs.id", ondelete="CASCADE"), nullable=False, index=True)
    issue_month   = Column(Date, nullable=False, index=True)
    horizon       = Column(Integer, nullable=False)
    target_month  = Column(Date, nullable=False)
    fill_now      = Column(Float, nullable=False)
    fill_pred     = Column(Float, nullable=False)
    fill_lo80     = Column(Float, nullable=False)
    fill_hi80     = Column(Float, nullable=False)
    p_critical    = Column(Float, nullable=False)
    status        = Column(String, nullable=False)
    model_version = Column(String, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
