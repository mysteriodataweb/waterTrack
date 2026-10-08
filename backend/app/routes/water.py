from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import get_db
from ..deps import require_api_key
from ..models import WaterSource
from ..schemas import (
    WaterSourceResponse,
    PaginatedSources,
    Status,
    AdminUpdateResponse,
)

router = APIRouter()


def _row_to_response(source: WaterSource, geom: str | None) -> WaterSourceResponse:
    """`geom` : GeoJSON déjà calculé par ST_AsGeoJSON dans la requête principale."""
    return WaterSourceResponse(
        id=source.id,
        longitude=source.longitude,
        latitude=source.latitude,
        zone=source.zone or "Ouagadougou",
        zone_detail=source.zone_detail or source.zone or None,
        superficie_km2=source.superficie_km2,
        ndwi_moyen=source.ndwi_moyen,
        risk_score=source.risk_score or 0.0,
        status=_normalize_status(source.status or "actif"),
        date_analyse=source.date_analyse,
        geometry=json.loads(geom) if geom else None,
    )


def _normalize_status(status: str) -> Status:
    s = status.lower()
    if "tari" in s:
        return "tari"
    if "risque" in s:
        return "à risque"
    if "actif" in s:
        return "actif"
    return "inconnu"


@router.get("/water-sources", response_model=PaginatedSources)
def get_water_sources(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    zone: str | None = None,
    status: str | None = None,
):
    query = select(WaterSource)
    if zone:
        query = query.where(WaterSource.zone == zone)
    if status:
        query = query.where(WaterSource.status == status)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    # Géométrie GeoJSON calculée dans la même requête (une seule requête par page).
    rows = db.execute(
        query.add_columns(func.ST_AsGeoJSON(WaterSource.geometry))
        .order_by(WaterSource.id).offset((page - 1) * page_size).limit(page_size)
    ).all()

    return PaginatedSources(
        total=total,
        page=page,
        page_size=page_size,
        items=[_row_to_response(s, geom) for s, geom in rows],
    )


@router.get("/water-sources/{source_id}", response_model=WaterSourceResponse)
def get_water_source(source_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        select(WaterSource, func.ST_AsGeoJSON(WaterSource.geometry)).where(WaterSource.id == source_id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Source non trouvée")
    return _row_to_response(*row)


@router.post("/admin/recompute", response_model=AdminUpdateResponse)
def recompute_all_scores(db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    """Recalcule risk_score/status des sources.

    v3 (si des prévisions existent) : statut = prévision à 1 mois du réservoir de la
    source, risk_score = probabilité calibrée d'atteindre le niveau critique.
    Sinon (repli v2) : calcul à partir de l'historique NDWI réel, décrit ci-dessous.

    On n'utilise plus de seuil absolu sur `ndwi_moyen` (moyenne toutes saisons
    confondues) : ce chiffre est dominé par la saisonnalité et ne dit rien de
    la santé d'une source. Voir `services/risk.py`.
    """
    from ..models import NdwiObservation
    from ..services.reservoirs import apply_forecasts_to_sources
    from ..services.risk import compute_risk_from_history

    updated = apply_forecasts_to_sources(db)
    if updated:
        db.commit()
        return AdminUpdateResponse(updated=updated, message=f"{updated} sources mises à jour (prévisions v3)")

    rows = db.execute(
        select(
            NdwiObservation.source_id,
            NdwiObservation.periode,
            NdwiObservation.saison,
            NdwiObservation.ndwi,
        )
    ).all()

    historique: dict[int, list[tuple[str, str | None, float | None]]] = {}
    for source_id, periode, saison, ndwi in rows:
        historique.setdefault(source_id, []).append((periode, saison, ndwi))

    sources = db.execute(select(WaterSource)).scalars().all()
    updated = 0
    for s in sources:
        res = compute_risk_from_history(historique.get(s.id, []), s.ndwi_moyen)
        s.risk_score = res["score"]
        s.status = res["status"]
        updated += 1
    db.commit()
    return AdminUpdateResponse(updated=updated, message=f"{updated} sources mises à jour")
