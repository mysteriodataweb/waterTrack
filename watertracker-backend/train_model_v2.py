"""
Modèle ML v2: Prédire QUAND une source va tarir
Non pas juste "est-ce risqué", mais "combien de périodes AVANT tarissement"
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score, mean_squared_error
from sklearn.preprocessing import StandardScaler, LabelEncoder
import joblib
import os

# ============ 1. CHARGER ET PRÉPARER ============
print("Chargement des données...")
df = pd.read_csv('data/historique/ndwi_burkina_enrichi.csv')
df = df.sort_values(['ville', 'periode'])

print(f"Dataset: {len(df)} lignes, {df['ville'].nunique()} régions, {df['periode'].nunique()} périodes")

# Encoder les variables catégorielles
le_ville  = LabelEncoder()
le_saison = LabelEncoder()
df['ville_encoded']  = le_ville.fit_transform(df['ville'])
df['saison_encoded'] = le_saison.fit_transform(df['saison'])

# Extraire année et trimestre
df[['annee', 'trimestre']] = df['periode'].str.split('-', expand=True)
df['annee'] = df['annee'].astype(int)
df['trimestre'] = df['trimestre'].str.extract(r'(\d+)').astype(int)

# ============ 2. FEATURE ENGINEERING: Historique + Tendance ============
print("\nFeature Engineering...")

# Lags (périodes antérieures)
df['ndwi_t1']       = df.groupby('ville')['ndwi_moyen'].shift(1)
df['ndwi_t2']       = df.groupby('ville')['ndwi_moyen'].shift(2)
df['ndwi_t3']       = df.groupby('ville')['ndwi_moyen'].shift(3)

# Tendances
df['pente_court']   = df['ndwi_moyen'] - df['ndwi_t1']  # Change court terme
df['pente_moyen']   = df['ndwi_moyen'] - df['ndwi_t3']  # Changement 3 périodes
df['ndwi_moy_ville'] = df.groupby('ville')['ndwi_moyen'].transform('mean')

# VARIABLE CIBLE: Combien de périodes avant NDWI < 0.2 ?
def calc_periods_until_dry(groupe_ndwi):
    """
    groupe_ndwi: array de NDWI pour une région (ex: 24 valeurs)
    Retourne: liste EXACTEMENT MÊME TAILLE avec périodes jusqu'à tarissement
    """
    temps_avant_sec = [np.nan] * len(groupe_ndwi)  # Initialiser avec NaN
    
    for i in range(len(groupe_ndwi)):
        future = groupe_ndwi[i+1:]
        if len(future) == 0:
            temps_avant_sec[i] = np.nan
            continue
            
        # Chercher première période où NDWI < 0.2
        idx = np.where(future < 0.2)[0]
        if len(idx) > 0:
            temps_avant_sec[i] = idx[0] + 1
        else:
            temps_avant_sec[i] = 999  # Pas de tarissement détecté
    
    return temps_avant_sec

print("Calcul de la cible: 'périodes_avant_tarissement'...")
df['periods_until_dry'] = df.groupby('ville', group_keys=False)['ndwi_moyen'].transform(
    lambda x: calc_periods_until_dry(x.values)
)

# Convertir 999 en "grand nombre"
df['periods_until_dry'] = df['periods_until_dry'].replace(999, 20)

print(f"\nDistribution periods_until_dry:")
print(f"  Min: {df['periods_until_dry'].min():.0f}")
print(f"  Max: {df['periods_until_dry'].max():.0f}")
print(f"  Médiane: {df['periods_until_dry'].median():.0f}")
print(f"  Mean: {df['periods_until_dry'].mean():.1f}")
print(f"\nExemples:")
print(df[df['ville'] == 'Ouagadougou'][['periode', 'ndwi_moyen', 'periods_until_dry']].head(15))

# ============ 3. NETTOYAGE ============
print("\nNettoyage des données...")
df_clean = df.dropna(subset=['ndwi_t1', 'ndwi_t2', 'periods_until_dry'])
print(f"Lignes pour entraînement: {len(df_clean)}")

# ============ 4. FEATURES & TARGET ============
features = [
    'ndwi_moyen',
    'ndwi_t1',
    'ndwi_t2',
    'ndwi_t3',
    'pente_court',
    'pente_moyen',
    'ndwi_moy_ville',
    'ndvi_moyen',
    'evi_moyen',
    'altitude',
    'humidite_sol',
    'temperature',
    'precipitation',
    'annee',
    'trimestre',
    'saison_encoded',
    'ville_encoded',
    'latitude',
    'longitude',
]

X = df_clean[features].fillna(0)
y = df_clean['periods_until_dry']

print(f"\nFeatures: {len(features)}")
print(f"Target shape: {y.shape}")

# ============ 5. SPLIT & SCALE ============
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled  = scaler.transform(X_test)

# ============ 6. ENTRAÎNER ============
print("\n=== ENTRAÎNEMENT ===")

models = {
    'Random Forest': RandomForestRegressor(
        n_estimators=100,
        max_depth=15,
        min_samples_split=5,
        random_state=42
    ),
    'Gradient Boosting': GradientBoostingRegressor(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=5,
        random_state=42
    ),
}

best_model = None
best_name = ''
best_mae = float('inf')

for name, model in models.items():
    print(f"\nEntraînement {name}...")
    
    if name == 'Gradient Boosting':
        model.fit(X_train_scaled, y_train)
        y_pred = model.predict(X_test_scaled)
    else:
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
    
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    
    print(f"  MAE:  {mae:.2f} périodes")
    print(f"  RMSE: {rmse:.2f} périodes")
    print(f"  R²:   {r2:.3f}")
    
    if mae < best_mae:
        best_mae = mae
        best_model = model
        best_name = name

# ============ 7. SAUVEGARDER ============
print(f"\n=== RÉSULTAT FINAL ===")
print(f"Meilleur modèle: {best_name}")
print(f"MAE: {best_mae:.2f} périodes")

os.makedirs('app/models', exist_ok=True)

# Sauvegarder uniquement le meilleur
joblib.dump(best_model, f'app/models/watertracker_rf_v2.pkl')
joblib.dump(scaler, 'app/models/scaler_v2.pkl')
joblib.dump(le_ville, 'app/models/encoder_ville_v2.pkl')
joblib.dump(le_saison, 'app/models/encoder_saison_v2.pkl')

print(f"\nModèles sauvegardés:")
print(f"  - app/models/watertracker_rf_v2.pkl")
print(f"  - app/models/scaler_v2.pkl")
print(f"  - app/models/encoder_ville_v2.pkl")
print(f"  - app/models/encoder_saison_v2.pkl")

# ============ 8. TESTS ============
print(f"\n=== TESTS ===")
test_cases = [
    {'ndwi': 0.5, 'desc': 'Eau abondante'},
    {'ndwi': 0.3, 'desc': 'Eau modérée'},
    {'ndwi': 0.1, 'desc': 'Eau faible'},
    {'ndwi': -0.2, 'desc': 'Très sec'},
]

for tc in test_cases:
    test_row = X_test.iloc[0:1].copy()
    test_row['ndwi_moyen'] = tc['ndwi']
    
    if best_name == 'Gradient Boosting':
        test_row_scaled = scaler.transform(test_row)
        pred = best_model.predict(test_row_scaled)[0]
    else:
        pred = best_model.predict(test_row)[0]
    
    pred = max(1, min(20, int(pred)))  # Clamp entre 1 et 20
    print(f"  NDWI={tc['ndwi']:.1f} ({tc['desc']:20s}) → {pred} périodes avant tarissement")
