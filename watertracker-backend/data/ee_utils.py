from __future__ import annotations

import ee
import os


PROXY_ENV_VARS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "GIT_HTTP_PROXY",
    "GIT_HTTPS_PROXY",
)
BROKEN_PROXY_MARKERS = ("127.0.0.1:9", "localhost:9")


def _clear_broken_proxy_settings() -> list[str]:
    cleared = []
    for var_name in PROXY_ENV_VARS:
        value = os.environ.get(var_name)
        if value and any(marker in value for marker in BROKEN_PROXY_MARKERS):
            os.environ.pop(var_name, None)
            cleared.append(var_name)
    return cleared


def init_earth_engine(project: str) -> None:
    """Initialize Earth Engine and raise a clearer error on network/auth issues."""
    try:
        cleared_proxy_vars = _clear_broken_proxy_settings()
        if cleared_proxy_vars:
            print(
                "Configuration proxy invalide detectee pour Earth Engine; "
                f"variables ignorees: {', '.join(cleared_proxy_vars)}"
            )
        ee.Initialize(project=project)
    except Exception as exc:
        message = (
            "Impossible d'initialiser Google Earth Engine.\n"
            "Cause probable: acces reseau/DNS vers les services Google indisponible "
            "ou credentials Earth Engine invalides/expirés.\n"
            "Verifiez d'abord la connectivite vers oauth2.googleapis.com, puis relancez "
            "`earthengine authenticate` si necessaire.\n"
            f"Erreur d'origine: {exc}"
        )
        raise RuntimeError(message) from exc
