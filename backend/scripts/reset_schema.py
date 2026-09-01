"""
Réinitialise le schéma des tables WaterTracker (v2) en base.

⚠️ DESTRUCTIF : supprime les anciennes tables `water_sources` et
`ndwi_observations` (et leurs données v1) puis les recrée avec le
nouveau schéma v2.

Usage :
  python -m scripts.reset_schema
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("reset")

from sqlalchemy import text

from app.database import engine, ensure_postgis, create_all


def reset() -> None:
    ensure_postgis()
    with engine.begin() as conn:
        # Supprimer dans l'ordre des dépendances (ndwi_observations d'abord).
        conn.execute(text("DROP TABLE IF EXISTS ndwi_observations CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS water_sources CASCADE"))
    create_all()
    logger.info("Schéma réinitialisé : water_sources + ndwi_observations recréées (v2).")


if __name__ == "__main__":
    reset()
