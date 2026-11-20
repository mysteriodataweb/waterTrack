"""
Conseils pour agir, construits sur les prévisions v3.

Remplace l'ancien texte rédigé par un modèle de langage à partir de l'analyse NDWI
par semestre, que l'audit du modèle v2 a jugée peu fiable. Ici, des règles fixes :

- chaque phrase reprend un chiffre de la prévision affichée (remplissage mesuré,
  fourchette à 80 %, probabilité de passer sous le seuil critique, mois de passage
  sous le seuil en saison sèche) : le message ne peut pas contredire la fiche ;
- le même état donne toujours le même message, vérifiable et testable ;
- les actions dépendent du niveau d'alerte et de la personne qui doit agir.

Niveaux, alignés sur les statuts de la carte :
  critique  : retenue presque à sec le mois prochain (statut « tari ») ;
  alerte    : plus d'une chance sur deux de passer sous le seuil le mois prochain (« à risque ») ;
  vigilance : pas d'alerte le mois prochain, mais un risque plus loin, une retenue
              encore sous le seuil qui remonte, ou un assèchement plus tôt que d'habitude ;
  normal    : aucune alerte dans les trois mois.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

from ml.forecasting import ALERT_PROBABILITY

AUDIENCES = {
    "communaute": "Habitants et usagers",
    "agent_terrain": "Agent de terrain",
    "ong": "ONG",
    "gouvernement": "Service de l'État",
}
AUDIENCE_FOR = {
    "communaute": "les habitants et usagers",
    "agent_terrain": "l'agent de terrain",
    "ong": "l'ONG",
    "gouvernement": "le service de l'État",
}
LEVELS = ("normal", "vigilance", "alerte", "critique")

WATCH_PROBABILITY = 0.20    # en dessous : pas de risque à signaler (comme la fiche du frontend)
WIDE_INTERVAL = 0.40        # fourchette à 80 % plus large que 40 points : prévision incertaine
FLOOD_FILL = 1.05           # au-dessus : l'eau déborde la surface de référence

MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
          "septembre", "octobre", "novembre", "décembre"]

# Raison du niveau -> jeu d'actions
ACTION_SET = {
    "dry": "crise", "below": "crise", "risk_next": "alerte",
    "risk_later": "anticipation", "early_drying": "anticipation",
    "watch": "surveillance", "refilling": "remontee", "ok": "normal",
}

ACTIONS: dict[str, dict[str, list[str]]] = {
    "crise": {
        "communaute": [
            "Réserver l'eau restante aux usages essentiels : besoins domestiques et abreuvement du bétail.",
            "Ne pas lancer de nouvelles cultures irriguées et limiter le pompage pour le maraîchage.",
            "Repérer dès maintenant le point d'eau de repli (forage, borne-fontaine, autre retenue) et organiser le trajet.",
        ],
        "agent_terrain": [
            "Visiter la retenue dans la semaine : photo depuis un point fixe, lecture de l'échelle si elle existe, "
            "motopompes en marche.",
            "Signaler si l'eau observée contredit la mesure satellite.",
            "Recenser les usagers qui dépendent de la retenue (villages, éleveurs, maraîchers) et leur point de repli.",
        ],
        "ong": [
            "Préparer l'approvisionnement de secours des usagers de cette retenue (citernes, remise en état "
            "des forages proches).",
            "Faire confirmer la situation sur place par un agent de terrain avant d'engager les moyens.",
            "Se coordonner avec la commune et le comité de gestion de l'eau.",
        ],
        "gouvernement": [
            "Classer la retenue parmi les sites en situation critique ce mois-ci.",
            "Arbitrer les prélèvements avec le comité de gestion : priorité aux besoins domestiques et au bétail, "
            "pompage pour l'irrigation suspendu ou limité.",
            "Prévenir la commune et les services techniques de l'eau.",
        ],
    },
    "alerte": {
        "communaute": [
            "Économiser l'eau dès maintenant et ne pas étendre les surfaces maraîchères.",
            "Repérer le point d'eau de repli le plus proche.",
        ],
        "agent_terrain": [
            "Programmer une visite pour confirmer le niveau (photo, échelle si elle existe).",
            "Noter les prélèvements en cours (motopompes, abreuvement).",
        ],
        "ong": [
            "Identifier les villages et les éleveurs qui dépendent de la retenue, et leurs solutions de repli.",
            "Préparer un plan d'approvisionnement, à déclencher si la visite de terrain confirme la baisse.",
        ],
        "gouvernement": [
            "Informer le comité de gestion et la commune ; envisager des tours d'eau pour les irrigants.",
            "Suivre la retenue de près au prochain bulletin.",
        ],
    },
    "anticipation": {
        "communaute": [
            "Pas d'urgence, mais commencer à économiser l'eau et éviter les nouvelles cultures irriguées de longue durée.",
            "Repérer le point d'eau de repli.",
        ],
        "agent_terrain": [
            "Prévoir une visite pour suivre la baisse.",
        ],
        "ong": [
            "Ajouter la retenue aux sites à préparer : identifier les usagers et leurs solutions de repli.",
        ],
        "gouvernement": [
            "Prévenir le comité de gestion du risque à venir et préparer les règles de partage de l'eau.",
        ],
    },
    "surveillance": {
        "communaute": ["Pas d'urgence : utiliser l'eau avec mesure."],
        "agent_terrain": ["Inclure la retenue dans la prochaine tournée si possible."],
        "ong": ["Pas d'action immédiate ; suivre la retenue au prochain bulletin."],
        "gouvernement": ["Pas d'action immédiate ; suivre la retenue au prochain bulletin."],
    },
    "remontee": {
        "communaute": ["Continuer à économiser l'eau tant que la retenue n'est pas remontée."],
        "agent_terrain": ["Vérifier au prochain passage que la retenue se remplit (photo depuis le même point)."],
        "ong": ["Maintenir les dispositifs de secours en place jusqu'à la remontée confirmée."],
        "gouvernement": ["Suivre la remontée au prochain bulletin avant de lever les restrictions."],
    },
    "normal": {
        "communaute": ["Pas d'action particulière. Le prochain bulletin paraît le mois prochain."],
        "agent_terrain": ["Pas de visite prioritaire."],
        "ong": ["Pas d'action nécessaire sur cette retenue."],
        "gouvernement": ["Pas d'action nécessaire sur cette retenue."],
    },
}

FLOOD_ACTIONS = {
    "communaute": "Prudence aux abords : l'eau couvre plus que la surface habituelle.",
    "agent_terrain": "Vérifier l'état de la digue et du déversoir au prochain passage.",
}


# --------------------------------------------------------------------------- #
# Mise en forme
# --------------------------------------------------------------------------- #
def month_label(value: str) -> str:
    """'2027-01' -> 'janvier 2027'."""
    p = pd.Period(value, "M")
    return f"{MONTHS[p.month - 1]} {p.year}"


def pct(value: float) -> str:
    return f"{round(value * 100)} %"


def risk_label(p: float) -> str:
    if p > 0.99:
        return "> 99 %"
    if p < 0.01:
        return "< 1 %"
    return pct(p)


def points(change: float) -> str:
    n = round(change * 100)
    if n == 0:
        return "stable"
    return f"{'+' if n > 0 else '−'}{abs(n)} point{'s' if abs(n) > 1 else ''}"


def when_label(target: str, today: date) -> str:
    """Échéance relative à aujourd'hui : les données ont un mois ou deux de retard sur le calendrier."""
    ahead = (pd.Period(target, "M") - pd.Period(today, "M")).n
    if ahead <= 0:
        return "dès maintenant"
    if ahead == 1:
        return "dans les semaines qui viennent"
    return f"avant {month_label(target)}"


# --------------------------------------------------------------------------- #
# Évaluation (indépendante du public)
# --------------------------------------------------------------------------- #
def _alarming(h: dict, critical: float) -> bool:
    return h["status"] != "actif" or h["p_critical"] >= ALERT_PROBABILITY or h["fill_pred"] < critical


def _earlier_than_usual(drying: Optional[dict]) -> bool:
    if not drying or not drying.get("critical_month"):
        return False
    usual = drying.get("usual_month")
    return usual is None or pd.Period(drying["critical_month"], "M") < pd.Period(usual, "M")


def assess(forecast: dict, drying: Optional[dict] = None) -> dict:
    """Niveau, raison, phrase de synthèse et mois d'échéance d'une retenue.

    `forecast` : prévision v3 telle que servie par l'API (issue_month, fill_now,
    critical_fill, horizons [{horizon, target_month, fill_pred, fill_lo80, fill_hi80,
    p_critical, status}]). `drying` : prévision d'assèchement (saison sèche) ou None.
    """
    hs = sorted(forecast["horizons"], key=lambda h: h["horizon"])
    critical, fill_now = forecast["critical_fill"], forecast["fill_now"]
    first, last = hs[0], hs[-1]
    m1, crit = month_label(first["target_month"]), pct(critical)
    later = next((h for h in hs[1:] if _alarming(h, critical)), None)
    worst = max(hs, key=lambda h: h["p_critical"])

    if first["status"] == "tari":
        level, reason, key = "critique", "dry", first
        headline = f"Retenue presque à sec prévue en {m1} (remplissage prévu {pct(first['fill_pred'])})."
    elif _alarming(first, critical) and fill_now < critical:
        level, reason, key = "alerte", "below", first
        headline = (f"Retenue déjà sous le seuil critique de {crit} ({pct(fill_now)}), "
                    f"et elle devrait y rester en {m1}.")
    elif _alarming(first, critical):
        level, reason, key = "alerte", "risk_next", first
        headline = f"Risque élevé ({risk_label(first['p_critical'])}) de passer sous le seuil critique de {crit} en {m1}."
    elif fill_now < critical:
        level, reason, key = "vigilance", "refilling", first
        headline = (f"Retenue encore sous le seuil critique de {crit}, mais elle devrait remonter "
                    f"à {pct(first['fill_pred'])} en {m1}.")
    elif later is not None:
        level, reason, key = "vigilance", "risk_later", later
        headline = (f"Pas d'alerte en {m1}, mais risque élevé ({risk_label(later['p_critical'])}) "
                    f"de passer sous le seuil critique en {month_label(later['target_month'])}.")
    elif worst["p_critical"] >= WATCH_PROBABILITY:
        level, reason, key = "vigilance", "watch", worst
        headline = (f"Pas d'alerte, mais un risque à surveiller : {risk_label(worst['p_critical'])} "
                    f"de passer sous le seuil critique en {month_label(worst['target_month'])}.")
    elif _earlier_than_usual(drying):
        level, reason, key = "vigilance", "early_drying", None
        usual = drying.get("usual_month")
        headline = (f"Pas d'alerte d'ici {month_label(last['target_month'])}, mais passage sous le seuil critique "
                    f"attendu en {month_label(drying['critical_month'])}, plus tôt que d'habitude"
                    + (f" ({month_label(usual)})." if usual else "."))
    else:
        level, reason, key = "normal", "ok", None
        headline = f"Aucune alerte prévue d'ici {month_label(last['target_month'])}."

    deadline = None
    if reason in ("dry", "below", "risk_next", "risk_later", "watch"):
        deadline = key["target_month"]
    elif reason == "early_drying":
        deadline = drying["critical_month"]
    return {"level": level, "reason": reason, "headline": headline, "deadline_month": deadline,
            "key_horizon": None if key is None else key["horizon"]}


def situation(forecast: dict, drying: Optional[dict], fill_change: Optional[float], key_horizon: Optional[int]) -> list[str]:
    """Les faits sur lesquels repose le conseil, avec leurs chiffres."""
    hs = sorted(forecast["horizons"], key=lambda h: h["horizon"])
    critical, fill_now = forecast["critical_fill"], forecast["fill_now"]
    now = f"Remplissage mesuré en {month_label(forecast['issue_month'])} : {pct(fill_now)} de la surface de référence"
    if fill_change is not None:
        now += f" ({points(fill_change)} en un mois)"
    if fill_now > FLOOD_FILL:
        now += " ; l'eau déborde la surface de référence (crue ou zone inondée)"
    lines = [now + "."]
    for h in hs:
        if h["horizon"] == 1 or h["horizon"] == key_horizon:
            lines.append(
                f"Prévu en {month_label(h['target_month'])} : {pct(h['fill_pred'])} "
                f"(8 fois sur 10 entre {pct(h['fill_lo80'])} et {pct(h['fill_hi80'])}), "
                f"risque de passer sous {pct(critical)} : {risk_label(h['p_critical'])}."
            )
    if drying:
        if drying.get("lasts_to_june"):
            lines.append(f"Saison sèche : devrait tenir jusqu'au retour des pluies, fin juin "
                         f"({risk_label(drying['p_lasts_to_june'])} de chances).")
        else:
            latest = drying.get("latest_80")
            usual = drying.get("usual_month")
            lines.append(
                f"Saison sèche : passage sous le seuil le plus probable en {month_label(drying['critical_month'])}"
                + (f" (8 fois sur 10 entre {month_label(drying['earliest_80'])} et "
                   f"{month_label(latest) if latest else 'après juin'})" if drying.get("earliest_80") else "")
                + f" ; d'habitude : {month_label(usual) if usual else "tient jusqu'à fin juin"}."
            )
    return lines


def build_advice(forecast: dict, drying: Optional[dict] = None, fill_change: Optional[float] = None,
                 today: Optional[date] = None, data_stale: bool = False, to_validate: bool = False) -> dict:
    """Conseil complet d'une retenue : synthèse, faits, actions et message à partager pour chaque public."""
    today = today or date.today()
    a = assess(forecast, drying)
    facts = situation(forecast, drying, fill_change, a["key_horizon"])
    hs = {h["horizon"]: h for h in forecast["horizons"]}

    # Échéance d'action : pas pour un simple risque à surveiller ni sans alerte
    when = None
    if a["reason"] in ("dry", "below"):
        when = "dès maintenant"
    elif a["reason"] in ("risk_next", "risk_later", "early_drying"):
        when = when_label(a["deadline_month"], today)

    caveats = []
    if data_stale:
        caveats.append(f"Dernières mesures : {month_label(forecast['issue_month'])}. "
                       "La situation a pu changer depuis : à vérifier sur place.")
    key = hs.get(a["key_horizon"]) if a["key_horizon"] else None
    if key and key["fill_hi80"] - key["fill_lo80"] >= WIDE_INTERVAL:
        caveats.append(f"Prévision incertaine pour {month_label(key['target_month'])} : la fourchette est large "
                       f"({pct(key['fill_lo80'])} à {pct(key['fill_hi80'])}).")
    if to_validate:
        caveats.append("Plan d'eau repéré par satellite, pas encore confirmé sur le terrain.")
    caveats.append("Surface en eau mesurée par satellite : une estimation, à confirmer sur place "
                   "avant une décision importante.")

    audiences = {}
    for audience, label in AUDIENCES.items():
        actions = list(ACTIONS[ACTION_SET[a["reason"]]][audience])
        if forecast["fill_now"] > FLOOD_FILL and audience in FLOOD_ACTIONS:
            actions.append(FLOOD_ACTIONS[audience])
        text = "\n".join([a["headline"], *facts, f"À faire pour {AUDIENCE_FOR[audience]} :",
                          *[f"- {s}" for s in actions],
                          *([f"Quand : {when}."] if when else []), *caveats])
        audiences[audience] = {"label": label, "actions": actions, "text": text}

    return {
        "level": a["level"],
        "reason": a["reason"],
        "headline": a["headline"],
        "situation": facts,
        "deadline_month": a["deadline_month"],
        "when": when,
        "caveats": caveats,
        "audiences": audiences,
    }
