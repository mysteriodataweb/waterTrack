"""
Recalculer les scores de risque en fonction des NDWI enrichis
Utilise les règles NDWI (fallback) plutôt que le modèle ML
"""
from app.database import SessionLocal
from app.models import WaterSource

# Définir les règles NDWI directement (pas besoin du modèle ML)
def get_risk_from_ndwi(ndwi):
    """Convertir NDWI en score de risque et statut"""
    if ndwi is None:
        return {'score': 0.5, 'status': 'inconnu'}
    if ndwi > 0.4:
        return {'score': 0.1, 'status': 'actif'}
    elif ndwi > 0.2:
        return {'score': 0.5, 'status': 'a risque'}
    else:
        return {'score': 0.9, 'status': 'tari'}

print("Recalcul des scores de risque basés sur les NDWI...")
db = SessionLocal()
sources = db.query(WaterSource).all()
print(f"Sources trouvees: {len(sources)}")

updated = 0
skipped = 0

for i, source in enumerate(sources):
    if source.ndwi_moyen is None:
        skipped += 1
    else:
        # Utiliser les règles NDWI
        result = get_risk_from_ndwi(source.ndwi_moyen)
        source.risk_score = result['score']
        source.status = result['status']
        updated += 1
    
    if (i + 1) % 100 == 0:
        print(f"  Traitement {i + 1}/{len(sources)}")

db.commit()
db.close()

print(f"\nResultats:")
print(f"  Mis a jour: {updated}")
print(f"  Ignores: {skipped}")

# Afficher quelques exemples
print("\nExemples:")
db = SessionLocal()
samples = db.query(WaterSource).limit(10).all()
for s in samples:
    ndwi_val = f"{s.ndwi_moyen:.3f}" if s.ndwi_moyen is not None else "None"
    print(f"  ID {s.id}: NDWI={ndwi_val}, status={s.status}, score={s.risk_score:.3f}")
db.close()
