import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import WaterSource
from ..services.prediction import PredictionService

router = APIRouter()


def _get_source_coordinates(db: Session, source_id: int):
    row = db.execute(
        text(
            """
            SELECT
                ST_X(ST_Centroid(geometry)) AS longitude,
                ST_Y(ST_Centroid(geometry)) AS latitude
            FROM water_sources
            WHERE id = :id AND geometry IS NOT NULL
            """
        ),
        {"id": source_id},
    ).first()

    if not row:
        return None, None

    return row.longitude, row.latitude


def _build_prediction_input(db: Session, source: WaterSource): 
    if source.ndwi_moyen is None:
        return None

    longitude, latitude = _get_source_coordinates(db, source.id)

    return {
        "ndwi_moyen": source.ndwi_moyen,
        "ndvi_moyen": 0,
        "latitude": latitude if latitude is not None else 12.36,
        "longitude": longitude if longitude is not None else -1.52,
        "saison": "seche",
        "annee": 2024,
        "semestre": 1,
    }


@router.get("/water-sources")
def get_water_sources(db: Session = Depends(get_db)):
    sources = db.query(WaterSource).all()
    result = []
    for source in sources:
        geom = db.execute(
            text("SELECT ST_AsGeoJSON(geometry) FROM water_sources WHERE id = :id"),
            {"id": source.id},
        ).scalar()
        result.append(
            {
                "id": source.id,
                "geometry": json.loads(geom) if geom else None,
                "ndwi_moyen": source.ndwi_moyen,
                "risk_score": source.risk_score,
                "status": source.status,
                "zone": source.zone,
                "date_analyse": source.date_analyse,
            }
        )
    return result


@router.get("/water-sources/{source_id}")
def get_water_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(WaterSource).filter(WaterSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source non trouvee")

    geom = db.execute(
        text("SELECT ST_AsGeoJSON(geometry) FROM water_sources WHERE id = :id"),
        {"id": source.id},
    ).scalar()
    return {
        "id": source.id,
        "geometry": json.loads(geom) if geom else None,
        "ndwi_moyen": source.ndwi_moyen,
        "risk_score": source.risk_score,
        "status": source.status,
        "zone": source.zone,
        "date_analyse": source.date_analyse,
    }


@router.post("/predict")
def predict_risk(data: dict, db: Session = Depends(get_db)):
    return PredictionService.get_risk_score(data)


@router.post("/update-all-scores")
def update_all_scores(db: Session = Depends(get_db)):
    sources = db.query(WaterSource).all()
    updated = 0

    for source in sources:
        data = _build_prediction_input(db, source)
        if data is None:
            source.risk_score = 0.5
            source.status = "inconnu"
        else:
            result = PredictionService.get_risk_score(data)
            source.risk_score = result["score"]
            source.status = result["status"]
        updated += 1

    db.commit()
    return {"updated": updated, "message": f"{updated} sources mises a jour"}
