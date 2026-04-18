import pandas as pd
import numpy as np
from pathlib import Path
# 1. Charger les données
BASE_DIR = Path(__file__).resolve().parent
DATA_CANDIDATES = [
    BASE_DIR / "data" / "data" / "historique" / "ndwi_burkina_complet.csv",
]

data_path = next((path for path in DATA_CANDIDATES if path.exists()), None)
if data_path is None:
    raise FileNotFoundError(
        "Aucun dataset trouve. Emplacements testes: "
        + ", ".join(str(path) for path in DATA_CANDIDATES)
    )

df = pd.read_csv(data_path)
print(f"Fichier charge : {data_path}")
print(f"Dataset chargé : {len(df)} lignes")
print(df.head())


df = df.sort_values(['ville', 'periode'])
df['ndwi_t1']    = df.groupby('ville')['ndwi_moyen'].shift(1)
df['ndwi_futur'] = df.groupby('ville')['ndwi_moyen'].shift(-1)

df['risk_score'] = df['ndwi_futur'].apply(lambda x:
    0.1 if pd.notna(x) and x > 0.4 else
    0.5 if pd.notna(x) and x > 0.2 else
    0.9 if pd.notna(x) else np.nan
)

print("=== Aperçu des données ===")
print(df[['ville', 'periode', 'ndwi_moyen', 'ndwi_t1', 'ndwi_futur', 'risk_score']].head(20))

print("\n=== Distribution risk_score ===")
print(df['risk_score'].value_counts())

print("\n=== Stats NDWI ===")
print(df['ndwi_moyen'].describe())

print("\n=== Stats NDWI futur ===")
print(df['ndwi_futur'].describe())

print(f"\nLignes totales       : {len(df)}")
print(f"Lignes sans NaN      : {df.dropna(subset=['ndwi_t1','ndwi_futur','risk_score']).shape[0]}")
print(f"Villes uniques       : {df['ville'].nunique()}")
print(f"Périodes uniques     : {df['periode'].nunique()}")