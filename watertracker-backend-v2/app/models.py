from __future__ import annotations

from datetime import datetime, date

from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, UniqueConstraint, Index
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
