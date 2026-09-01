"""Calcul du risque de tarissement à partir de l'historique NDWI réel.

Pourquoi ce module existe
-------------------------
L'ancien calcul (`RuleBasedRiskService`) appliquait des seuils absolus
(NDWI > 0.4 = actif, > 0.2 = à risque) sur `ndwi_moyen`, c'est-à-dire la
moyenne de TOUTES les périodes confondues. Or au Burkina Faso le signal est
dominé par la saisonnalité :

    saison sèche (S1) : NDWI moyen ~0.08
    saison des pluies (S2) : NDWI moyen ~0.35

Moyenner les deux produit un nombre qui mesure surtout « quelle proportion de
l'historique est en saison des pluies », pas la santé de la source. Résultat
observé en production : des sources passées de -0.16 à +0.65 (en nette
amélioration) étaient étiquetées « tari », et l'unique source « actif » était
la seule dont la tendance en saison sèche était négative.

Méthode retenue
---------------
On raisonne sur la SAISON SÈCHE uniquement : c'est la période de soudure, celle
qui révèle si un point d'eau tient ou non. Deux signaux :

1. le NIVEAU : NDWI de la dernière saison sèche connue ;
2. la DÉRIVE : moyenne des 2 dernières saisons sèches moins la moyenne des
   saisons sèches les plus anciennes (tendance pluriannuelle à saison
   comparable, ce qui neutralise la saisonnalité).
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

DRY_SEASON = "seche"

# Seuils de niveau (NDWI en saison sèche).
LEVEL_DRY = 0.0        # en dessous : plus de signature d'eau en saison sèche
LEVEL_FRAGILE = 0.15   # en dessous : tient à peine la saison sèche

# Seuil de dérive pluriannuelle jugée préoccupante.
DRIFT_ALERT = -0.05

# Bornes de normalisation du score continu.
LEVEL_SAFE = 0.30      # niveau considéré comme sain
LEVEL_WORST = -0.20    # niveau considéré comme totalement sec
DRIFT_WORST = -0.20    # dérive considérée comme maximale


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _mean(values: Sequence[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def compute_risk_from_history(
    observations: Iterable[tuple[str, Optional[str], Optional[float]]],
    ndwi_moyen: Optional[float] = None,
) -> dict:
    """Calcule statut + score à partir de (periode, saison, ndwi).

    `observations` : itérable de tuples (periode, saison, ndwi).
    `ndwi_moyen` : repli si l'historique de saison sèche est insuffisant.
    """
    dry = sorted(
        ((periode, ndwi) for periode, saison, ndwi in observations
         if saison == DRY_SEASON and ndwi is not None),
        key=lambda row: row[0],
    )
    values = [ndwi for _, ndwi in dry]

    # Historique insuffisant : on reste prudent et explicite.
    if len(values) < 2:
        if ndwi_moyen is None:
            return {"score": 0.5, "status": "inconnu", "niveau_seche": None,
                    "derive_seche": None, "methode": "historique insuffisant"}
        niveau = float(ndwi_moyen)
        level_risk = _clamp((LEVEL_SAFE - niveau) / (LEVEL_SAFE - LEVEL_WORST))
        return {
            "score": round(level_risk, 3),
            "status": "tari" if niveau < LEVEL_DRY else ("à risque" if niveau < LEVEL_FRAGILE else "actif"),
            "niveau_seche": None,
            "derive_seche": None,
            "methode": "repli ndwi_moyen (pas assez de saisons sèches)",
        }

    niveau = float(values[-1])
    recent = _mean(values[-2:]) or niveau
    # Les saisons sèches "anciennes" = tout sauf les 3 plus récentes ;
    # si l'historique est court, on prend la plus ancienne disponible.
    older_pool = values[:-3] if len(values) >= 4 else values[:1]
    ancien = _mean(older_pool) or recent
    derive = float(recent - ancien)

    if niveau < LEVEL_DRY:
        status = "tari"
    elif niveau < LEVEL_FRAGILE or derive < DRIFT_ALERT:
        status = "à risque"
    else:
        status = "actif"

    level_risk = _clamp((LEVEL_SAFE - niveau) / (LEVEL_SAFE - LEVEL_WORST))
    trend_risk = _clamp(-derive / -DRIFT_WORST)
    score = round(_clamp(0.7 * level_risk + 0.3 * trend_risk), 3)

    return {
        "score": score,
        "status": status,
        "niveau_seche": round(niveau, 4),
        "derive_seche": round(derive, 4),
        "methode": "saison sèche : niveau + dérive pluriannuelle",
    }
