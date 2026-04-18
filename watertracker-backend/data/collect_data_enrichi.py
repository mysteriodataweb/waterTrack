import ee
import csv
import time
from pathlib import Path

from ee_utils import init_earth_engine

init_earth_engine(project="water-492400")

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "historique"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "ndwi_burkina_enrichi.csv"
CSV_FIELDS = [
    "ville",
    "province",
    "longitude",
    "latitude",
    "periode",
    "saison",
    "debut",
    "fin",
    "ndwi_moyen",
    "ndvi_moyen",
    "evi_moyen",
    "precipitation",
    "temperature",
    "altitude",
    "humidite_sol",
]

import csv

# Charger les données déjà extraites
if OUTPUT_FILE.exists():
    with OUTPUT_FILE.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_data = list(reader)
    print(f"Données existantes chargées : {len(all_data)} lignes")
else:
    all_data = []
def write_csv(rows):
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

# Toutes les communes du Burkina
gaul = ee.FeatureCollection('FAO/GAUL/2015/level2') \
         .filter(ee.Filter.eq('ADM0_NAME', 'Burkina Faso'))

communes_info = gaul.getInfo()['features']
print(f"Nombre total de communes : {len(communes_info)}")

# Périodes trimestrielles (plus de données que semestriel)
periodes = []
for annee in range(2019, 2025):
    periodes += [
        {'label': f'{annee}-T1', 'debut': f'{annee}-01-01', 'fin': f'{annee}-03-31', 'saison': 'seche'},
        {'label': f'{annee}-T2', 'debut': f'{annee}-04-01', 'fin': f'{annee}-06-30', 'saison': 'transition'},
        {'label': f'{annee}-T3', 'debut': f'{annee}-07-01', 'fin': f'{annee}-09-30', 'saison': 'pluies'},
        {'label': f'{annee}-T4', 'debut': f'{annee}-10-01', 'fin': f'{annee}-12-31', 'saison': 'transition'},
    ]

print(f"Nombre de périodes : {len(periodes)}")

all_data = []

# Traiter par batch de 20 communes pour éviter les erreurs mémoire
batch_size = 20
commune_batches = [
    communes_info[i:i+batch_size] 
    for i in range(0, len(communes_info), batch_size)
]

print(f"Nombre de batches : {len(commune_batches)}")

for batch_idx, batch in enumerate(commune_batches[1:], start=1):
    print(f"\nBatch {batch_idx+1}/{len(commune_batches)}...")

    # Créer une FeatureCollection pour ce batch
    batch_features = ee.FeatureCollection([
        ee.Feature(
            ee.Geometry(c['geometry']),
            {
                'ADM2_NAME': c['properties'].get('ADM2_NAME'),
                'ADM1_NAME': c['properties'].get('ADM1_NAME'),
            }
        ) for c in batch
    ])

    for p in periodes:
        try:
            # Image Sentinel-2
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                   .filterBounds(batch_features) \
                   .filterDate(p['debut'], p['fin']) \
                   .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
                   .median()

            # Indices satellitaires
            ndwi = s2.normalizedDifference(['B3', 'B8']).rename('NDWI')
            ndvi = s2.normalizedDifference(['B8', 'B4']).rename('NDVI')
            evi  = s2.expression(
                '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
                {'NIR': s2.select('B8'), 'RED': s2.select('B4'), 'BLUE': s2.select('B2')}
            ).rename('EVI')

            # Précipitations ERA5
            era5 = ee.ImageCollection('ECMWF/ERA5_LAND/MONTHLY_AGGR') \
                     .filterDate(p['debut'], p['fin']) \
                     .mean()

            precipitation = era5.select('total_precipitation_sum').rename('precipitation')
            temperature   = era5.select('temperature_2m').rename('temperature')

            # Altitude SRTM
            srtm     = ee.Image('USGS/SRTMGL1_003')
            altitude = srtm.select('elevation').rename('altitude')

            # Humidité du sol SMAP
            smap = ee.ImageCollection('NASA/SMAP/SPL4SMGP/008') \
                     .filterDate(p['debut'], p['fin']) \
                     .mean()
            
            humidite = smap.select('sm_surface').rename('humidite_sol')

            # Combiner toutes les variables
            composite = ndwi.addBands(ndvi) \
                            .addBands(evi) \
                            .addBands(precipitation) \
                            .addBands(temperature) \
                            .addBands(altitude) \
                            .addBands(humidite)

            # Extraire les stats par commune
            results = composite.reduceRegions(
                collection = batch_features,
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
                    'ville':         props.get('ADM2_NAME'),
                    'province':      props.get('ADM1_NAME'),
                    'longitude':     longitude,
                    'latitude':      latitude,
                    'periode':       p['label'],
                    'saison':        p['saison'],
                    'debut':         p['debut'],
                    'fin':           p['fin'],
                    'ndwi_moyen':    props.get('NDWI'),
                    'ndvi_moyen':    props.get('NDVI'),
                    'evi_moyen':     props.get('EVI'),
                    'precipitation': props.get('precipitation'),
                    'temperature':   props.get('temperature'),
                    'altitude':      props.get('altitude'),
                    'humidite_sol':  props.get('humidite_sol'),
                })

            time.sleep(1)

        except Exception as e:
            print(f"  → Erreur batch {batch_idx+1} période {p['label']}: {e}")
            continue

    # Sauvegarder après chaque batch
    write_csv(all_data)
    print(f"  → Batch {batch_idx+1} sauvegardé ({len(all_data)} lignes au total)")
    time.sleep(2)

# Dataset final
write_csv(all_data)

print(f"\n=== Dataset final ===")
print(f"Lignes    : {len(all_data)}")
print(f"Colonnes  : {len(CSV_FIELDS)}")
print(f"Communes  : {len({row['ville'] for row in all_data})}")
print(f"Périodes  : {len({row['periode'] for row in all_data})}")
print(all_data[:5])
