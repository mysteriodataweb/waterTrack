from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from .config import settings

# En-tête attendu : `X-API-Key: <clé>`
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """Protège les endpoints d'écriture avec une clé API simple.

    En production, `settings.api_key` doit être une valeur forte.
    """
    expected = settings.api_key
    if expected == "change-me-in-production":
        # En mode dev sans clé configurée, on accepte par défaut mais on log.
        return api_key or "dev"
    if not api_key or api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide",
        )
    return api_key
