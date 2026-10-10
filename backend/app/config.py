from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration centralisée, chargée depuis le fichier `.env`."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Base de données
    database_url: str = "postgresql+pg8000://user:password@localhost:5432/watertracker"

    # Sécurité
    api_key: str = "change-me-in-production"
    cors_origins: str = ""
    # Expression régulière d'origines autorisées, en plus de la liste : utile pour un hébergeur
    # qui donne une adresse par déploiement (Vercel).
    cors_origin_regex: str = ""

    # Services externes
    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3.8-27b"
    openroute_api_key: str = ""

    # Google Earth Engine
    gee_project: str = "water-492400"
    # Clé JSON d'un compte de service (chemin du fichier ou contenu JSON) pour le serveur.
    # Vide : identifiants utilisateur locaux (`earthengine authenticate`).
    gee_service_account_key: str = ""
    watch_center_lat: float = 12.3647
    watch_center_lng: float = -1.5221
    watch_radius_m: int = 50000

    # Scheduler : la mise à jour mensuelle v3 est vérifiée toutes les `collect_hours` heures ;
    # elle ne collecte un mois qu'une fois, dès qu'ERA5-Land et CHIRPS l'ont publié.
    scheduler_enabled: bool = False
    collect_hours: int = 168

    # Modèle v3 : seuil de niveau critique (part de la surface de référence).
    # Doit correspondre au seuil d'entraînement (CRITICAL_FILL du notebook) : le changer
    # impose de ré-entraîner le modèle, sinon les probabilités d'alerte n'ont plus de sens.
    critical_fill: float = 0.20

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS_ORIGINS est une liste séparée par des virgules."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def watch_center(self) -> tuple[float, float]:
        return (self.watch_center_lat, self.watch_center_lng)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
