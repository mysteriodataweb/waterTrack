import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.svm import SVR
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
import joblib
import os

# 1. Charger les données
df =pd.read_csv('D:\\Dossiers\\WaterTracker_Project\\watertracker-backend\\data\\historique\\ndwi_sources_historique.csv')
df = df.dropna(subset=['ndwi_moyen'])
print(f"Dataset : {len(df)} lignes")

# 2. Encoder
le_saison   = LabelEncoder()
df['saison_encoded'] = le_saison.fit_transform(df['saison'])
df['annee']          = df['periode'].str[:4].astype(int)
df['semestre']       = df['periode'].str[-1].astype(int)

# 3. Feature engineering PAR SOURCE
df = df.sort_values(['source_id', 'periode'])

df['ndwi_t1']        = df.groupby('source_id')['ndwi_moyen'].shift(1)
df['ndwi_t2']        = df.groupby('source_id')['ndwi_moyen'].shift(2)
df['ndwi_t3']        = df.groupby('source_id')['ndwi_moyen'].shift(3)
df['tendance']       = df['ndwi_moyen'] - df['ndwi_t1']
df['tendance_long']  = df['ndwi_moyen'] - df['ndwi_t3']
df['ndwi_moy_src']   = df.groupby('source_id')['ndwi_moyen'].transform('mean')
df['ndwi_futur']     = df.groupby('source_id')['ndwi_moyen'].shift(-1)

# 4. Seuils relatifs basés sur la distribution réelle
p33 = df['ndwi_futur'].quantile(0.33)
p66 = df['ndwi_futur'].quantile(0.66)

print(f"\n=== Seuils calibrés ===")
print(f"NDWI min  : {df['ndwi_futur'].min():.4f}")
print(f"Seuil p33 : {p33:.4f} → en dessous = risque élevé")
print(f"Seuil p66 : {p66:.4f} → au dessus  = risque faible")
print(f"NDWI max  : {df['ndwi_futur'].max():.4f}")

def get_risk(ndwi):
    if pd.isna(ndwi):
        return np.nan
    if ndwi >= p66:
        return 0.1
    elif ndwi >= p33:
        return 0.5
    else:
        return 0.9

df['risk_score'] = df['ndwi_futur'].apply(get_risk)

print(f"\n=== Distribution risk_score ===")
print(df['risk_score'].value_counts())

# 5. Nettoyer
df = df.dropna(subset=['ndwi_t1', 'ndwi_t2', 'ndwi_futur', 'risk_score'])
print(f"\nLignes pour entraînement : {len(df)}")

features = [
    'ndwi_t1',
    'ndwi_t2',
    'ndwi_t3',
    'tendance',
    'tendance_long',
    'ndwi_moy_src',
    'ndvi_moyen',
    'latitude',
    'longitude',
    'saison_encoded',
    'annee',
    'semestre'
]

X = df[features].fillna(0)
y = df['risk_score']

# 6. Split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# 7. Comparer les modèles
scaler         = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled  = scaler.transform(X_test)

models = {
    'Random Forest':     RandomForestRegressor(n_estimators=100, random_state=42),
    'Gradient Boosting': GradientBoostingRegressor(n_estimators=100, random_state=42),
    'SVR':               SVR(kernel='rbf', C=1.0),
}

print("\n=== Comparaison des modèles ===")
best_model = None
best_r2    = -999
best_name  = ''

for name, model in models.items():
    if name == 'SVR':
        model.fit(X_train_scaled, y_train)
        y_pred = model.predict(X_test_scaled)
    else:
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    r2  = r2_score(y_test, y_pred)
    print(f"{name:25} → MAE: {mae:.4f} | R²: {r2:.4f}")

    if r2 > best_r2:
        best_r2    = r2
        best_model = model
        best_name  = name

print(f"\nMeilleur modèle : {best_name} (R²={best_r2:.4f})")

# 8. Importance features
rf = models['Random Forest']
importances = pd.DataFrame({
    'feature':    features,
    'importance': rf.feature_importances_
}).sort_values('importance', ascending=False)

print("\n=== Importance des features ===")
print(importances.to_string(index=False))

# 9. Sauvegarder
os.makedirs('app/models', exist_ok=True)
joblib.dump(best_model, 'app/models/watertracker_rf.pkl')
joblib.dump(scaler,     'app/models/scaler.pkl')
joblib.dump(le_saison,  'app/models/encoder_saison.pkl')
joblib.dump({'p33': p33, 'p66': p66}, 'app/models/seuils.pkl')

print(f"\nModèle '{best_name}' sauvegardé ✅")