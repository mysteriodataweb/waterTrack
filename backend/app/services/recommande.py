from __future__ import annotations

from .llm import PROFILS, generer_recommandation_groq


def _risque_niveau(prediction: dict) -> str:
    ndwi = prediction.get("ndwi_actuel") or 0
    if ndwi <= 0.2:
        return "CRITIQUE"
    if ndwi <= 0.4:
        return "ÉLEVÉ"
    if ndwi <= 0.7:
        return "MODÉRÉ"
    return "FAIBLE"


def _regle_recommandation(prediction: dict, profil: str) -> str:
    niveau = _risque_niveau(prediction)
    vitesse = prediction.get("vitesse_degradation", "stable")
    date_tarissement = prediction.get("date_tarissement") or "non estimée"

    base = f"Niveau de risque {niveau}. Vitesse de dégradation : {vitesse}. "
    if niveau == "CRITIQUE":
        delai = "Agir immédiatement (moins d'une semaine)."
        action = "Sécuriser un approvisionnement alternatif d'urgence."
    elif niveau == "ÉLEVÉ":
        delai = "Agir dans les prochaines semaines."
        action = "Surveiller de plus près et prévoir un plan de repli."
    elif niveau == "MODÉRÉ":
        delai = "Agir ce trimestre."
        action = "Maintenir une surveillance régulière et sensibiliser."
    else:
        delai = "Agir de façon préventive ce semestre."
        action = "Entretenir la source et suivre l'évolution NDWI."

    cibles = {
        "ong": f"{action} Mobiliser les ressources et coordonner l'acheminement d'eau vers la zone touchée ({delai}).",
        "gouvernement": f"{action} Prioriser cette source dans les plans d'urgence et débloquer des financements ({delai}).",
        "agent_terrain": f"{action} Effectuer une visite terrain et remonter l'état réel de la source ({delai}).",
        "communaute": f"{action} Organiser l'entraide et économiser l'eau dès maintenant ({delai}).",
    }
    return base + f"Date de tarissement estimée : {date_tarissement}. " + cibles.get(profil, cibles["communaute"])


def generer_recommandation(prediction: dict, profil: str) -> str:
    """Recommandation via Groq, avec repli sur des règles déterministes."""
    if profil not in PROFILS:
        profil = "communaute"
    ia = generer_recommandation_groq(prediction, profil)
    return ia if ia else _regle_recommandation(prediction, profil)


def generer_toutes_recommandations(prediction: dict) -> dict[str, str]:
    return {profil: generer_recommandation(prediction, profil) for profil in PROFILS}
