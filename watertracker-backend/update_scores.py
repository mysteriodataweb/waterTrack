from sqlalchemy import text

from app.database import SessionLocal, engine, Base
from app.models import WaterSource
from app.services.prediction import PredictionService

Base.metadata.create_all(bind=engine)


def get_source_coordinates(db, source_id: int):
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


def build_prediction_input(db, source: WaterSource):
    if source.ndwi_moyen is None:
        return None

    longitude, latitude = get_source_coordinates(db, source.id)

    return {
        "ndwi_moyen": source.ndwi_moyen,
        "ndvi_moyen": 0,
        "latitude": latitude if latitude is not None else 12.36,
        "longitude": longitude if longitude is not None else -1.52,
        "saison": "seche",
        "annee": 2024,
        "semestre": 1,
    }


def update_risk_scores():
    db = SessionLocal()
    predictor = PredictionService

    sources = db.query(WaterSource).all()
    updated = 0

    for source in sources:
        data = build_prediction_input(db, source)
        if data is None:
            source.risk_score = 0.5
            source.status = "inconnu"
        else:
            result = predictor.get_risk_score(data)
            source.risk_score = result["score"]
            source.status = result["status"]
        updated += 1

    db.commit()
    db.close()
    print(f"{updated} sources mises a jour")


if __name__ == "__main__":
    update_risk_scores()
