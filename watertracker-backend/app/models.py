from sqlalchemy import Column, Integer, String, Float, DateTime
from geoalchemy2 import Geometry
from datetime import datetime
from .database import Base

class WaterSource(Base):
    __tablename__ = "water_sources"

    id           = Column(Integer, primary_key=True, index=True)
    geometry     = Column(Geometry('GEOMETRY', srid=4326))
    ndwi_moyen   = Column(Float, nullable=True)
    zone         = Column(String, default="Ouagadougou")
    date_analyse = Column(String, nullable=True)
    risk_score   = Column(Float, default=0.0)
    status       = Column(String, default="actif")
    created_at   = Column(DateTime, default=datetime.utcnow)
