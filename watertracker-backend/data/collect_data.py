import ee
import pandas as pd
import os
import time

from ee_utils import init_earth_engine

init_earth_engine(project="water-492400")

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

gaul = ee.FeatureCollection('FAO/GAUL/2015/level2') \
         .filter(ee.Filter.eq('ADM0_NAME', 'Burkina Faso')) \
         .limit(50)

os.makedirs('data/historique', exist_ok=True)

all_data = []

for p in periodes:
    print(f"Traitement {p['label']}...")

    try:
        image = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                  .filterBounds(gaul) \
                  .filterDate(p['debut'], p['fin']) \
                  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
                  .median()

        ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI')
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        composite = ndwi.addBands(ndvi)

        results = composite.reduceRegions(
            collection = gaul,
            reducer    = ee.Reducer.mean(),
            scale      = 500
        )

        features = results.getInfo()['features']

        for f in features:
            props = f['properties']
            geom  = f['geometry']

            if geom and geom['type'] == 'Polygon':
                coords    = geom['coordinates'][0]
                longitude = sum(c[0] for c in coords) / len(coords)
                latitude  = sum(c[1] for c in coords) / len(coords)
            else:
                longitude = None
                latitude  = None

            all_data.append({
                'ville':      props.get('ADM2_NAME'),
                'province':   props.get('ADM1_NAME'),
                'longitude':  longitude,
                'latitude':   latitude,
                'periode':    p['label'],
                'saison':     p['saison'],
                'debut':      p['debut'],
                'fin':        p['fin'],
                'ndwi_moyen': props.get('NDWI'),
                'ndvi_moyen': props.get('NDVI')
            })

        print(f"  → {len(features)} communes traitées ✅")
        time.sleep(2)  # évite de surcharger GEE

    except Exception as e:
        print(f"  → Erreur {p['label']}: {e}")
        continue

df = pd.DataFrame(all_data)
df.to_csv('data/historique/ndwi_burkina_complet.csv', index=False)
print(f"\nDataset final : {len(df)} lignes sauvegardées ✅")
print(df.head())
