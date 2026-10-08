from __future__ import annotations

import logging
import secrets
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from .config import settings

logger = logging.getLogger(__name__)

DEFAULT_API_KEY = "change-me-in-production"

# En-tête attendu : `X-API-Key: <clé>`
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """Protège les endpoints d'écriture avec une clé API simple.

    En production, `settings.api_key` doit être une valeur forte.
    """
    expected = settings.api_key
    if expected == DEFAULT_API_KEY:
        # Mode dev sans clé configurée : accepté, mais signalé à chaque appel.
        logger.warning("API_KEY par défaut : endpoint d'écriture accessible sans authentification")
        return api_key or "dev"
    # compare_digest : comparaison à temps constant (pas de fuite par chronométrage).
    if not api_key or not secrets.compare_digest(api_key.encode(), expected.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide",
        )
    return api_key
