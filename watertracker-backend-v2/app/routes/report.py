from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import NdwiObservation, WaterSource
from ..schemas import (
    PeriodRow,
    ReportSummary,
    ReportTopSourceRow,
    ReportZoneRow,
    Status,
)

router = APIRouter()


@router.get("/report/summary", response_model=ReportSummary)
def get_report_summary(db: Session = Depends(get_db)):
    """Synthèse agrégée réelle pour le rapport : tendance NDWI par période, statuts,
    zones, top sources à risque — tout est calculé depuis les tables de production."""

    # Tendance NDWI par période (moyenne de toutes les sources).
    periodes_raw = db.execute(
        select(
            NdwiObservation.periode,
            func.avg(NdwiObservation.ndwi),
            func.count(func.distinct(NdwiObservation.source_id)),
        )
        .group_by(NdwiObservation.periode)
        .order_by(NdwiObservation.periode)
    ).all()

    periodes = [
        PeriodRow(
            periode=p,
            ndwi_moyen=round(float(ndwi), 4),
            nb_sources=int(nb),
        )
        for p, ndwi, nb in periodes_raw
    ]

    # Statuts des sources.
    statuses_raw = db.execute(
        select(WaterSource.status, func.count(WaterSource.id)).group_by(WaterSource.status)
    ).all()
    statut: dict[str, int] = {}
    for status, count in statuses_raw:
        statut[status or "actif"] = int(count)

    total_sources = int(
        db.execute(select(func.count(WaterSource.id))).scalar() or 0
    )

    superficie_totale = float(
        db.execute(select(func.coalesce(func.sum(WaterSource.superficie_km2), 0.0))).scalar() or 0.0
    )

    ndwi_global = db.execute(select(func.avg(NdwiObservation.ndwi))).scalar()

    nb_observations = int(
        db.execute(select(func.count(NdwiObservation.id))).scalar() or 0
    )

    zones_raw = db.execute(
        text(
            "SELECT COALESCE(NULLIF(zone_detail, ''), zone, 'Ouagadougou') AS z, COUNT(*) "
            "FROM water_sources GROUP BY z ORDER BY count DESC"
        )
    ).all()
    zones = [ReportZoneRow(zone=str(z), count=int(c)) for z, c in zones_raw]

    top_risque_raw = db.execute(
        select(WaterSource)
        .order_by(WaterSource.risk_score.desc(), WaterSource.id)
        .limit(5)
    ).scalars().all()
    top_risque = [
        ReportTopSourceRow(
            id=s.id,
            zone_detail=(s.zone_detail or s.zone or "Ouagadougou"),
            status=s.status or "actif",
            risk_score=s.risk_score or 0.0,
            ndwi_moyen=s.ndwi_moyen,
        )
        for s in top_risque_raw
    ]

    return ReportSummary(
        periode=periodes[-1].periode if periodes else "—",
        date_generation=date.today(),
        total_sources=total_sources,
        statut=statut,
        superficie_totale_km2=round(superficie_totale, 4),
        ndwi_moyen_global=round(float(ndwi_global), 4) if ndwi_global is not None else None,
        nb_observations=nb_observations,
        periodes=periodes,
        zones=zones,
        top_risque=top_risque,
    )