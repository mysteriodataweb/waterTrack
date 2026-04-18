"""Test du modèle ML"""
from app.services.prediction import PredictionService

print("Test du modèle ML:")
print("=" * 50)

# Tester une prédiction
test_data = {
    'ndwi_moyen': 0.5,      # Eau présente
    'ndvi_moyen': 0.3,
    'latitude': 12.36,
    'longitude': -1.52,
    'saison': 'seche',
    'annee': 2028,
    'semestre': 1,
}

try:
    result = PredictionService.get_risk_score(test_data)
    print(f"\nModèle: {PredictionService.__class__.__name__}")
    print(f"Type de service actif: {type(PredictionService).__name__}")
    print(f"\nTest avec NDWI=0.5:")
    print(f"  Score: {result['score']}")
    print(f"  Statut: {result['status']}")
    print(f"\nModele ML: FONCTIONNEL ✓" if result['score'] != 0.1 else "Modele ML: FALLBACK NDWI")
    
except Exception as e:
    print(f"Erreur: {e}")
    print("Modele ML: NON FONCTIONNEL ✗")
