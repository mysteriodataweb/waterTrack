"""API v3 : réservoirs, surfaces mensuelles, prévisions, bulletin, validation de l'inventaire."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import require_api_key
from ..models import FillForecast, Reservoir, ReservoirSource, WaterAreaObservation, WaterSource
from ..schemas import (
    AreaPoint,
    FillForecast as FillForecastSchema,
    MonthlyUpdateRequest,
    ReservoirHistory,
    ReservoirSummary,
    ValidationUpdate,
)
from ..services import reservoirs as svc

router = APIRouter()

MONTH_PATTERN = r"^\d{4}-\d{2}$"


def _month(value: Optional[str]) -> Optional[date]:
    return None if value is None else pd.Period(value, "M").to_timestamp().date()


def _forecast_payload(db: Session, reservoir_id: str, source_id: Optional[int] = None) -> dict:
    issue = svc.latest_issue_month(db)
    if issue is None:
        raise HTTPException(status_code=503, detail="Aucune prévision en base : exécuter scripts/load_v3.py")
    rows = db.execute(
        select(FillForecast).where(FillForecast.reservoir_id == reservoir_id, FillForecast.issue_month == issue)
        .order_by(FillForecast.horizon)
    ).scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="Pas de prévision pour ce réservoir")
    a_ref = db.get(Reservoir, reservoir_id).a_ref_ha
    return {
        "reservoir_id": reservoir_id,
        "source_id": source_id,
        "issue_month": issue.strftime("%Y-%m"),
        "fill_now": rows[0].fill_now,
        "critical_fill": settings.critical_fill,
        "model_version": rows[0].model_version,
        "horizons": [{
            "horizon": r.horizon, "target_month": r.target_month.strftime("%Y-%m"),
            "fill_pred": round(r.fill_pred, 4), "fill_lo80": round(r.fill_lo80, 4),
            "fill_hi80": round(r.fill_hi80, 4), "p_critical": round(r.p_critical, 4), "status": r.status,
            "area_pred_ha": None if a_ref is None else round(r.fill_pred * a_ref, 2),
        } for r in rows],
    }


# --------------------------------------------------------------------------- #
# Lecture
# --------------------------------------------------------------------------- #
@router.get("/reservoirs", response_model=list[ReservoirSummary])
def list_reservoirs(
    db: Session = Depends(get_db),
    origin: Optional[Literal["application", "JRC"]] = None,
    validation: Optional[Literal["a_valider", "valide", "rejete"]] = None,
):
    query = select(
        Reservoir,
        func.ST_Y(func.ST_Centroid(Reservoir.geometry)),
        func.ST_X(func.ST_Centroid(Reservoir.geometry)),
    ).order_by(Reservoir.id)
    if origin:
        query = query.where(Reservoir.origin == origin)
    if validation:
        query = query.where(Reservoir.validation == validation)
    rows = db.execute(query).all()

    sources = pd.DataFrame(db.execute(select(ReservoirSource.reservoir_id, ReservoirSource.source_id)).all(),
                           columns=["reservoir_id", "source_id"]).groupby("reservoir_id")["source_id"].apply(list)
    last_month = db.execute(select(func.max(WaterAreaObservation.month))).scalar()
    last = {}
    if last_month is not None:
        last = dict(db.execute(select(WaterAreaObservation.reservoir_id, WaterAreaObservation.fill)
                               .where(WaterAreaObservation.month == last_month)).all())
    fc = svc.forecasts_frame(db)
    status = {} if fc.empty else fc[fc["horizon"] == fc["horizon"].min()].set_index("reservoir_id")["status"].to_dict()

    return [ReservoirSummary(
        id=r.id, origin=r.origin, validation=r.validation, validation_note=r.validation_note,
        modelable=r.modelable, a_ref_ha=r.a_ref_ha, lat=lat, lon=lon,
        source_ids=sources.get(r.id, []),
        last_month=None if last_month is None else last_month.strftime("%Y-%m"),
        fill_last=None if last.get(r.id) is None else round(last[r.id], 4),
        status=status.get(r.id),
    ) for r, lat, lon in rows]


@router.get("/reservoirs/{reservoir_id}/history", response_model=ReservoirHistory)
def reservoir_history(
    reservoir_id: str,
    db: Session = Depends(get_db),
    start: Optional[str] = Query(default=None, pattern=MONTH_PATTERN),
    end: Optional[str] = Query(default=None, pattern=MONTH_PATTERN),
):
    reservoir = db.get(Reservoir, reservoir_id)
    if reservoir is None:
        raise HTTPException(status_code=404, detail="Réservoir non trouvé")
    query = select(WaterAreaObservation).where(WaterAreaObservation.reservoir_id == reservoir_id)
    if start:
        query = query.where(WaterAreaObservation.month >= _month(start))
    if end:
        query = query.where(WaterAreaObservation.month <= _month(end))
    obs = db.execute(query.order_by(WaterAreaObservation.month)).scalars().all()
    return ReservoirHistory(
        reservoir_id=reservoir_id, a_ref_ha=reservoir.a_ref_ha,
        points=[AreaPoint(month=o.month.strftime("%Y-%m"), area_ha=o.area_ha, fill=o.fill,
                          area_source=o.area_source, volume_m3=o.volume_m3, precip_mm=o.precip_mm) for o in obs],
    )


@router.get("/reservoirs/{reservoir_id}/forecast", response_model=FillForecastSchema)
def reservoir_forecast(reservoir_id: str, db: Session = Depends(get_db)):
    if db.get(Reservoir, reservoir_id) is None:
        raise HTTPException(status_code=404, detail="Réservoir non trouvé")
    return _forecast_payload(db, reservoir_id)


@router.get("/water-sources/{source_id}/forecast", response_model=FillForecastSchema)
def source_forecast(source_id: int, db: Session = Depends(get_db)):
    """Prévision v3 pour une source de l'application (via le réservoir physique auquel elle appartient)."""
    if db.get(WaterSource, source_id) is None:
        raise HTTPException(status_code=404, detail="Source non trouvée")
    reservoir_id = svc.reservoir_of_source(db, source_id)
    if reservoir_id is None:
        raise HTTPException(status_code=404, detail="Source non rattachée à un réservoir modélisé")
    return _forecast_payload(db, reservoir_id, source_id)


@router.get("/bulletin")
def monthly_bulletin(
    db: Session = Depends(get_db),
    month: Optional[str] = Query(default=None, pattern=MONTH_PATTERN, description="Mois d'émission (défaut : dernier)"),
    format: Literal["json", "csv"] = "json",
    include_rejected: bool = False,
):
    """Bulletin mensuel : état et prévisions de toutes les retenues, classées par risque."""
    try:
        bulletin = svc.build_bulletin(db, _month(month), include_rejected=include_rejected)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if format == "csv":
        return Response(
            content=svc.bulletin_to_csv(bulletin), media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="bulletin_{bulletin["issue_month"]}.csv"'},
        )
    return bulletin


# --------------------------------------------------------------------------- #
# Administration
# --------------------------------------------------------------------------- #
@router.patch("/admin/reservoirs/{reservoir_id}/validation", response_model=ReservoirSummary)
def validate_reservoir(
    reservoir_id: str,
    payload: ValidationUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Validation de l'inventaire par le gestionnaire (ex. plans d'eau ajoutés depuis JRC)."""
    reservoir = db.get(Reservoir, reservoir_id)
    if reservoir is None:
        raise HTTPException(status_code=404, detail="Réservoir non trouvé")
    reservoir.validation = payload.validation
    reservoir.validation_note = payload.note
    reservoir.validated_at = datetime.utcnow()
    db.commit()
    return next(r for r in list_reservoirs(db=db) if r.id == reservoir_id)


@router.post("/admin/monthly-update")
def trigger_monthly_update(payload: MonthlyUpdateRequest, _: str = Depends(require_api_key)):
    """Collecte satellite v3 d'un mois (défaut : dernier disponible) puis prévisions et statuts."""
    from ..collectors.monthly import run_monthly_update

    try:
        return run_monthly_update(month=payload.month, force=payload.force)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
