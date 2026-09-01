from __future__ import annotations

import logging
from typing import Optional

from ..config import settings

logger = logging.getLogger(__name__)

PROFILS = {
    "ong": "une ONG humanitaire qui gère des interventions d'urgence eau",
    "gouvernement": "une autorité gouvernementale locale responsable de la gestion de l'eau",
    "agent_terrain": "un agent terrain qui se déplace physiquement vers les sources",
    "communaute": "une communauté rurale qui dépend directement de cette source",
}


def _build_prompt(prediction: dict, profil: str) -> str:
    date_tarissement = prediction.get("date_tarissement") or "non estimée"
    vitesse = prediction.get("vitesse_degradation", "stable")
    ndwi_actuel = prediction.get("ndwi_actuel", 0)
    confiance = prediction.get("confiance", 0)
    proba = prediction.get("probabilite_tarissement", 0)

    return f"""
Tu es un expert en gestion des ressources en eau en Afrique subsaharienne,
spécialisé sur le Burkina Faso.

Données d'une source d'eau analysée par satellite :
- NDWI actuel : {ndwi_actuel} (entre -1 et 1, plus c'est élevé plus il y a de l'eau)
- Vitesse de dégradation : {vitesse}
- Date de tarissement estimée : {date_tarissement}
- Probabilité de tarissement : {proba}%
- Niveau de confiance de la prédiction : {confiance}%

Tu t'adresses à {PROFILS.get(profil, PROFILS['communaute'])}.

Génère une recommandation concrète, courte (3-4 phrases maximum),
en français simple, adaptée exactement à ce profil.
Indique clairement :
1. Le niveau de risque
2. L'action prioritaire à mener
3. Le délai recommandé pour agir
"""


def generer_recommandation_groq(prediction: dict, profil: str) -> Optional[str]:
    """Recommandation via Groq. Retourne None si le service est indisponible."""
    if not settings.groq_api_key:
        return None
    try:
        from groq import Groq
    except ModuleNotFoundError:
        return None

    if profil not in PROFILS:
        profil = "communaute"

    try:
        client = Groq(api_key=settings.groq_api_key)
        message = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[{"role": "user", "content": _build_prompt(prediction, profil)}],
            max_tokens=500,
        )
        return message.choices[0].message.content.strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Recommandation Groq indisponible : %s", exc)
        return None
