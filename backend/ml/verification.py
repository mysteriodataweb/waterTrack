"""
Vérification des prévisions déjà émises, une fois leur mois cible mesuré.

Chaque mise à jour mensuelle mesure le remplissage réel d'un nouveau mois : les
prévisions émises 1, 2 et 3 mois plus tôt pour ce mois peuvent alors être jugées.
C'est le bilan réel du modèle en service, sur des mois qu'il n'avait jamais vus.

Référence : la normale saisonnière du réservoir, c'est-à-dire la médiane de son
remplissage pour le même mois calendaire les années précédentes (la référence la
plus exigeante du notebook). Le modèle n'apporte quelque chose que s'il fait mieux.

Lecture des alertes : une alerte est un statut « à risque » ou « tari » ; l'événement
est un remplissage observé sous le niveau critique. Les entrées en crise sont les
prévisions émises alors que la retenue était encore au-dessus du niveau critique.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ALERT_STATUSES = ("à risque", "tari")


def seasonal_normal(observed: pd.DataFrame) -> pd.DataFrame:
    """Normale de chaque mois : médiane du même mois calendaire les années précédentes (NaN la 1re année)."""
    o = observed.dropna(subset=["fill"]).copy()
    o["month"] = pd.to_datetime(o["month"])
    o = o.sort_values(["reservoir_id", "month"])
    o["cal_month"] = o["month"].dt.month
    o["normal"] = o.groupby(["reservoir_id", "cal_month"])["fill"].transform(
        lambda s: s.expanding().median().shift(1))
    return o[["reservoir_id", "month", "fill", "normal"]]


def match(forecasts: pd.DataFrame, observed: pd.DataFrame, critical: float) -> pd.DataFrame:
    """Une ligne par prévision dont le mois cible est mesuré : prévu, observé, normale, alerte."""
    obs = seasonal_normal(observed).rename(columns={"month": "target_month", "fill": "observed"})
    f = forecasts.assign(target_month=pd.to_datetime(forecasts["target_month"]),
                         issue_month=pd.to_datetime(forecasts["issue_month"]))
    v = f.merge(obs, on=["reservoir_id", "target_month"], how="inner")
    v["abs_err"] = (v["fill_pred"] - v["observed"]).abs()
    v["normal_abs_err"] = (v["normal"] - v["observed"]).abs()
    v["inside_80"] = (v["observed"] >= v["fill_lo80"]) & (v["observed"] <= v["fill_hi80"])
    v["event"] = v["observed"] < critical
    v["alert"] = v["status"].isin(ALERT_STATUSES)
    v["onset"] = v["fill_now"] >= critical          # encore au-dessus du seuil à l'émission
    return v


def _share(num: float, den: float):
    return num / den if den else None


def scores(v: pd.DataFrame) -> dict:
    """Erreur, gain sur la normale, intervalle, probabilités et alertes d'un groupe de prévisions."""
    ref = v[v["normal"].notna()]
    mae_ref, normal_mae = ref["abs_err"].mean(), ref["normal_abs_err"].mean()
    hits = int((v["alert"] & v["event"]).sum())
    alerts, events = int(v["alert"].sum()), int(v["event"].sum())
    onset = v[v["onset"]]
    out = {
        "n": len(v),
        "mae": v["abs_err"].mean(),
        "normal_mae": normal_mae,
        "skill_vs_normal": None if not len(ref) or not normal_mae else 1 - mae_ref / normal_mae,
        "coverage_80": v["inside_80"].mean(),
        "brier": ((v["p_critical"] - v["event"]) ** 2).mean(),
        "events": events,
        "alerts": alerts,
        "hits": hits,
        "false_alarms": alerts - hits,
        "precision": _share(hits, alerts),
        "recall": _share(hits, events),
        "crisis_onsets": int(onset["event"].sum()),
        "onsets_detected": int((onset["event"] & onset["alert"]).sum()),
    }
    return {k: (None if isinstance(x, float) and np.isnan(x) else (round(x, 4) if isinstance(x, float) else x))
            for k, x in out.items()}


def summarise(v: pd.DataFrame, by: str) -> list[dict]:
    """Scores par horizon, mois cible ou mois d'émission (dates au format AAAA-MM)."""
    out = []
    for key, grp in v.groupby(by):
        label = key.strftime("%Y-%m") if isinstance(key, pd.Timestamp) else (int(key) if by == "horizon" else key)
        out.append({by: label, **scores(grp)})
    return out
