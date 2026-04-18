import json
from sqlalchemy import text
from app.database import SessionLocal, engine, Base
from app.models import WaterSource
from geoalchemy2.shape import from_shape
from shapely.geometry import shape

Base.metadata.create_all(bind=engine)

with engine.begin() as connection:
    # Existing databases may already have a POLYGON-only column, which rejects
    # the MultiPolygon features present in the source GeoJSON.
    connection.execute(
        text(
            """
            ALTER TABLE water_sources
            ALTER COLUMN geometry
            TYPE geometry(GEOMETRY, 4326)
            USING geometry::geometry
            """
        )
    )

def import_geojson(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    print(f"Nombre de features trouvees : {len(features)}")

    db = SessionLocal()
    count = 0

    for feature in features:
        try:
            geom = shape(feature['geometry'])
            props = feature.get('properties', {})

            source = WaterSource(
                geometry     = from_shape(geom, srid=4326),
                ndwi_moyen   = props.get('ndwi_moyen', None),
                zone         = props.get('zone', 'Ouagadougou'),
                date_analyse = props.get('date_analyse', '2024-01-01/2024-03-31'),
                risk_score   = 0.0,
                status       = 'actif'
            )
            db.add(source)
            count += 1

        except Exception as e:
            print(f"Erreur sur feature {count}: {e}")
            continue

    db.commit()
    db.close()
    print(f"{count} sources importees avec succes")

if __name__ == "__main__":
    filepath = "data/water_sources_ouaga_2024.geojson"
    import_geojson(filepath)

