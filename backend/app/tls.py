"""Certificats TLS du système pour tous les appels sortants (GEE, Groq, ORS).

Sous Windows, un antivirus qui inspecte HTTPS (Avast, Kaspersky...) signe le
trafic avec sa propre autorité, inconnue de `certifi` : les appels échouent
alors en `SSLCertVerificationError` / « Connection error ». `truststore` fait
utiliser le magasin de certificats du système, sans désactiver la vérification.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
_done = False


def use_system_certificates() -> None:
    global _done
    if _done:
        return
    try:
        import truststore
    except ImportError:
        logger.info("truststore absent : certificats certifi par défaut")
        return
    truststore.inject_into_ssl()
    _done = True
