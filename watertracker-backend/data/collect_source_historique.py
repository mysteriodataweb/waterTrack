import csv
import time
from pathlib import Path

import ee

ee.Initialize(project="water-492400")

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "historique"
OUTPUT_PATH = OUTPUT_DIR / "ndwi_sources_historique.csv"
CSV_FIELDS = [
    "source_id",
    "longitude",
    "latitude",
    "periode",
    "saison",
    "debut",
    "fin",
    "ndwi_moyen",
    "ndvi_moyen",
]


def write_csv(rows):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

# Zone Ouagadougou
ouaga = ee.Geometry.Point([-1.5221, 12.3647])
zone  = ouaga.buffer(50000)

# Recréer les 278 sources
image2024 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
              .filterBounds(zone) \
              .filterDate('2024-01-01', '2024-03-31') \
              .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10)) \
              .median()

ndwi2024 = image2024.normalizedDifference(['B3', 'B8']).gt(0.2)

sources = ndwi2024.updateMask(ndwi2024).reduceToVectors(
    geometry      = zone,
    scale         = 20,
    maxPixels     = 1e8,
    bestEffort    = True
)

print(f"Sources chargées : {sources.size().getInfo()}")

# 10 périodes
periodes = [
    {'label': '2020-S1', 'debut': '2020-01-01', 'fin': '2020-06-30', 'saison': 'seche'},
    {'label': '2020-S2', 'debut': '2020-07-01', 'fin': '2020-12-31', 'saison': 'pluies'},
    {'label': '2021-S1', 'debut': '2021-01-01', 'fin': '2021-06-30', 'saison': 'seche'},
    {'label': '2021-S2', 'debut': '2021-07-01', 'fin': '2021-12-31', 'saison': 'pluies'},
    {'label': '2022-S1', 'debut': '2022-01-01', 'fin': '2022-06-30', 'saison': 'seche'},
    {'label': '2022-S2', 'debut': '2022-07-01', 'fin': '2022-12-31', 'saison': 'pluies'},
    {'label': '2023-S1', 'debut': '2023-01-01', 'fin': '2023-06-30', 'saison': 'seche'},
    {'label': '2023-S2', 'debut': '2023-07-01', 'fin': '2023-12-31', 'saison': 'pluies'},
    {'label': '2024-S1', 'debut': '2024-01-01', 'fin': '2024-06-30', 'saison': 'seche'},
    {'label': '2024-S2', 'debut': '2024-07-01', 'fin': '2024-12-31', 'saison': 'pluies'},
]

all_data = []

for p in periodes:
    print(f"Traitement {p['label']}...")
    try:
        image = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                  .filterBounds(zone) \
                  .filterDate(p['debut'], p['fin']) \
                  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
                  .median()

        ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI')
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')

        stats = ndwi.addBands(ndvi).reduceRegions(
            collection = sources,
            reducer    = ee.Reducer.mean(),
            scale      = 20
        )

        def add_props(f):
            centroid = f.geometry().centroid(1).coordinates()
            return f.set({
                'periode':   p['label'],
                'saison':    p['saison'],
                'debut':     p['debut'],
                'fin':       p['fin'],
                'longitude': centroid.get(0),
                'latitude':  centroid.get(1)
            })

        result   = stats.map(add_props)
        features = result.getInfo()['features']

        for f in features:
            props = f['properties']
            all_data.append({
                'source_id':  props.get('label', None),
                'longitude':  props.get('longitude'),
                'latitude':   props.get('latitude'),
                'periode':    p['label'],
                'saison':     p['saison'],
                'debut':      p['debut'],
                'fin':        p['fin'],
                'ndwi_moyen': props.get('NDWI'),
                'ndvi_moyen': props.get('NDVI'),
            })

        print(f"  → {len(features)} sources traitées ")

        # Sauvegarde intermédiaire
        write_csv(all_data)

        time.sleep(2)

    except Exception as e:
        print(f"  → Erreur {p['label']}: {e}")
        continue

write_csv(all_data)

print(f"\n=== Dataset final ===")
print(f"Lignes    : {len(all_data)}")
print(f"Sources   : {len({row['source_id'] for row in all_data})}")
print(f"Périodes  : {len({row['periode'] for row in all_data})}")
print(all_data[:5])
