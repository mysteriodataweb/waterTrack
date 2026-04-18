"""
Enrichir les sources d'eau avec les données NDWI les plus récentes
de l'historique satellite (ndwi_burkina_enrichi.csv par région)
"""
import pandas as pd
from app.database import SessionLocal
from app.models import WaterSource
from geoalchemy2.shape import to_shape

# Charger l'historique NDWI régional
print("Chargement de l'historique NDWI regional...")
df_historique = pd.read_csv('data/historique/ndwi_burkina_enrichi.csv')
print(f"Total lignes d'historique: {len(df_historique)}")
print(f"Periodes disponibles: {sorted(df_historique['periode'].unique())}")

# Garder les plus récentes (triées par année et trimestre)
df_historique[['year', 'trimestre']] = df_historique['periode'].str.split('-', expand=True)
df_historique['year'] = df_historique['year'].astype(int)
df_historique['trimestre'] = df_historique['trimestre'].str.extract(r'(\d+)').astype(int)
df_recent = df_historique.sort_values(['year', 'trimestre', 'ville'], ascending=[False, False, True])

print(f"Donnees groupees par ville/province")

# Récupérer toutes les sources
print("\nRecuperation des sources d'eau...")
db = SessionLocal()
sources = db.query(WaterSource).all()
print(f"Sources trouvees: {len(sources)}")

# Enrichissement par spatial matching (centroide source vs coordinates historique)
print("\nEnrichissement par appariement spatial...")
updated_count = 0
skipped_count = 0

for i, source in enumerate(sources):
    try:
        # Extraire centroid de la géometrie
        geom = to_shape(source.geometry)
        if geom.geom_type == 'Polygon':
            lon, lat = geom.centroid.x, geom.centroid.y
        elif geom.geom_type == 'Point':
            lon, lat = geom.x, geom.y
        else:
            lon, lat = geom.centroid.x, geom.centroid.y
        
        # Chercher la données historique la plus proche
        # Rayon de ~15km = 0.2 degrés
        df_match = df_recent[
            (abs(df_recent['longitude'] - lon) < 0.2) &
            (abs(df_recent['latitude'] - lat) < 0.2)
        ]
        
        if not df_match.empty:
            # Prendre la première (la plus récente après tri)
            row = df_match.iloc[0]
            source.ndwi_moyen = float(row['ndwi_moyen']) if pd.notna(row['ndwi_moyen']) else None
            source.date_analyse = row['periode']
            updated_count += 1
        else:
            # Fallback: chercher simplement la plus proche (sans limite distance)
            df_all = df_historique.copy()
            df_all['dist'] = ((df_all['longitude'] - lon)**2 + (df_all['latitude'] - lat)**2)**0.5
            df_closest = df_all.nsmallest(1, 'dist')
            
            if not df_closest.empty:
                row = df_closest.iloc[0]
                source.ndwi_moyen = float(row['ndwi_moyen']) if pd.notna(row['ndwi_moyen']) else None
                source.date_analyse = row['periode']
                updated_count += 1
            else:
                skipped_count += 1
    
    except Exception as e:
        print(f"  Erreur source {source.id}: {e}")
        skipped_count += 1
    
    if (i + 1) % 100 == 0:
        print(f"  Traitement en cours... {i + 1}/{len(sources)}")

# Commit les changements
db.commit()
db.close()

print(f"\nResultats:")
print(f"  OK: {updated_count} sources enrichies avec NDWI")
print(f"  SKIP: {skipped_count} sources sans donnees")

# Afficher quelques exemples
print("\nExemples de sources enrichies:")
db = SessionLocal()
samples = db.query(WaterSource).filter(WaterSource.ndwi_moyen != None).limit(10).all()
for s in samples:
    if s.ndwi_moyen:
        print(f"  ID {s.id}: NDWI={s.ndwi_moyen:.3f}, Date={s.date_analyse}")
db.close()
