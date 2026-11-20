"""
Réentraînement annuel du modèle v3, avec contrôle avant mise en service.

À lancer une fois par an, après la saison des pluies, sur le panel mensuel de la base
(qui s'allonge chaque mois) : `scripts/retrain.py`.

Principe : le modèle en service (le « champion ») fixe la configuration. Chaque
estimateur est cloné (mêmes hyperparamètres, même formulation niveau / variation),
seules les données changent. La surface de référence, la calibration radar et les
variables statiques restent celles du champion : le taux de remplissage garde la
même définition et l'historique reste comparable.

Évaluation honnête du « challenger » sur la dernière saison (les `window_months`
derniers mois cibles), comme dans le notebook (§9-11) :
  1. modèles quantiles entraînés sur les mois antérieurs à l'année de calibration,
     correction conforme calculée sur cette année ;
  2. modèles réentraînés sur tout ce qui précède la fenêtre, prévisions de la fenêtre ;
  3. notes avec `ml/verification.py`, comme les prévisions réellement émises.

Contrôle avant mise en service (toutes les conditions doivent être remplies) :
  - à 1 mois, le challenger fait mieux que la normale saisonnière ;
  - à 2 et 3 mois, il ne fait pas plus de 5 % moins bien qu'elle ;
  - à chaque horizon, 70 à 90 % des observations tombent dans l'intervalle à 80 % ;
  - là où le champion a un bilan réel suffisant sur la fenêtre (prévisions émises
    puis vérifiées), le challenger ne fait pas plus de 2 % moins bien que lui sur
    les mêmes prévisions.

Le modèle candidat est ensuite entraîné sur TOUTES les données (fenêtre comprise),
avec une correction conforme recalculée sur la fenêtre. Sa mise en service reste
une décision humaine : publier le paquet et mettre à jour son empreinte.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.base import clone

from . import features as F
from . import verification as V
from .forecasting import status_from

H1_MIN_SKILL = 0.0              # à 1 mois : strictement meilleur que la normale saisonnière
LONG_MIN_SKILL = -0.05          # à 2-3 mois : au plus 5 % moins bien que la normale
COVERAGE_RANGE = (0.70, 0.90)   # intervalle nominal à 80 %
CHAMPION_TOLERANCE = 0.02       # au plus 2 % d'erreur en plus que le bilan réel du champion
MIN_CHAMPION_ROWS = 200         # en dessous, le bilan réel du champion est trop maigre pour juger
CONFORMAL_LEVEL = 0.80


@dataclass
class Retraining:
    """Résultat d'un réentraînement : décision, contrôles, notes et paquet candidat."""
    decision: str
    checks: list[dict]
    challenger: dict[int, dict]
    normal: dict[int, dict]
    champion: dict[int, dict]
    window: tuple[str, str]
    bundle: dict = field(repr=False)
    forecasts: pd.DataFrame = field(repr=False, default=None)   # prévisions du challenger, notées


def _month(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y-%m")


# --------------------------------------------------------------------------- #
# Entraînement d'un horizon (configuration du champion)
# --------------------------------------------------------------------------- #
def training_rows(panel: pd.DataFrame, horizon: int, climatology: dict, static: pd.DataFrame,
                  train_end: str) -> pd.DataFrame:
    rows = F.build_rows(panel, horizon, climatology, static, train_end=train_end)
    return rows.dropna(subset=["y", "fill_l0"]).reset_index(drop=True)


def fit_horizon(template: dict, rows: pd.DataFrame, features: list[str], critical: float) -> dict:
    """Clone et réentraîne les quatre estimateurs d'un horizon (médiane, deux quantiles, alerte)."""
    X, base = rows[features], rows["fill_l0"]
    delta = rows["y"] - base
    mode = template["target_mode"]
    return {
        "median": clone(template["median"]).fit(X, delta if mode == "delta" else rows["y"]),
        "target_mode": mode,
        "q_lo": clone(template["q_lo"]).fit(X, delta),
        "q_hi": clone(template["q_hi"]).fit(X, delta),
        "classifier": clone(template["classifier"]).fit(X, (rows["y"] < critical).astype(int)),
        "calibrator": None,
        "alert_threshold": template.get("alert_threshold"),
    }


def conformal_correction(models: dict, rows: pd.DataFrame, features: list[str]) -> float:
    """Élargissement de l'intervalle pour couvrir 80 % des observations de `rows` (Romano et al., 2019)."""
    X, base = rows[features], rows["fill_l0"].values
    lo = np.clip(models["q_lo"].predict(X) + base, 0, 1.5)
    hi = np.clip(models["q_hi"].predict(X) + base, 0, 1.5)
    s = np.maximum(lo - rows["y"].values, rows["y"].values - hi)
    n = len(s)
    return float(np.quantile(s, min(1.0, np.ceil((n + 1) * CONFORMAL_LEVEL) / n)))


def predict_rows(models: dict, conformal_q: float, rows: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Prévisions au format de `fill_forecasts`, pour les noter comme les prévisions émises."""
    X, base = rows[features], rows["fill_l0"].values
    med = models["median"].predict(X) + (base if models["target_mode"] == "delta" else 0)
    pred = np.clip(med, 0, 1.5)
    p = models["classifier"].predict_proba(X)[:, 1]
    return pd.DataFrame({
        "reservoir_id": rows["reservoir_id"].values,
        "issue_month": rows["date"].values,
        "horizon": rows["horizon"].values,
        "target_month": rows["target_date"].values,
        "fill_now": base,
        "fill_pred": pred,
        "fill_lo80": np.clip(models["q_lo"].predict(X) + base - conformal_q, 0, 1.5),
        "fill_hi80": np.clip(models["q_hi"].predict(X) + base + conformal_q, 0, 1.5),
        "p_critical": p,
        "status": status_from(pd.Series(pred), pd.Series(p)),
    })


# --------------------------------------------------------------------------- #
# Contrôle avant mise en service
# --------------------------------------------------------------------------- #
def _normal_scores(v: pd.DataFrame) -> dict:
    """Notes de la normale saisonnière seule, sur les mêmes lignes."""
    ref = v[v["normal"].notna()]
    return {"n": len(ref), "mae": ref["normal_abs_err"].mean() if len(ref) else None}


def gate(challenger: dict[int, dict], champion: dict[int, dict], champion_mae_same_rows: dict[int, float],
         challenger_mae_same_rows: dict[int, float]) -> list[dict]:
    """Liste des contrôles, chacun avec sa valeur, son seuil et son résultat."""
    checks = []
    for h, s in sorted(challenger.items()):
        skill = None if s["skill_vs_normal"] is None else float(s["skill_vs_normal"])
        floor = H1_MIN_SKILL if h == 1 else LONG_MIN_SKILL
        checks.append({"check": f"h={h} : gain sur la normale saisonnière", "value": skill,
                       "threshold": f"> {floor:+.0%}" if h == 1 else f">= {floor:+.0%}",
                       "passed": bool(skill is not None and (skill > floor if h == 1 else skill >= floor))})
        cov = None if s["coverage_80"] is None else float(s["coverage_80"])
        checks.append({"check": f"h={h} : part des observations dans l'intervalle à 80 %", "value": cov,
                       "threshold": f"{COVERAGE_RANGE[0]:.0%} à {COVERAGE_RANGE[1]:.0%}",
                       "passed": bool(cov is not None and COVERAGE_RANGE[0] <= cov <= COVERAGE_RANGE[1])})
        n_champ = champion.get(h, {}).get("n", 0)
        if n_champ >= MIN_CHAMPION_ROWS:
            ratio = float(challenger_mae_same_rows[h] / champion_mae_same_rows[h] - 1)
            checks.append({"check": f"h={h} : erreur comparée au bilan réel du champion ({n_champ} prévisions)",
                           "value": ratio, "threshold": f"<= {CHAMPION_TOLERANCE:+.0%}",
                           "passed": bool(ratio <= CHAMPION_TOLERANCE)})
    return checks


# --------------------------------------------------------------------------- #
# Réentraînement complet
# --------------------------------------------------------------------------- #
def retrain(panel: pd.DataFrame, champion: dict, champion_record: pd.DataFrame | None = None,
            window_months: int = 12, critical: float | None = None) -> Retraining:
    """Évalue un challenger sur la dernière saison, décide, et entraîne le candidat sur tout le panel.

    `champion_record` : prévisions réellement émises par le champion et vérifiées
    (`ml.verification.match`), facultatif.
    """
    critical = champion["critical_fill"] if critical is None else critical
    features, static = champion["features"], champion["static"]
    panel = panel[panel["reservoir_id"].isin(static.index)].copy()
    panel["date"] = pd.to_datetime(panel["date"])
    observed = panel.rename(columns={"date": "month"})[["reservoir_id", "month", "fill"]]

    last = panel.loc[panel["fill"].notna(), "date"].max().to_period("M")
    window_start = (last - (window_months - 1)).to_timestamp()
    calib_start = (last - (2 * window_months - 1)).to_timestamp()
    before_window = _month(window_start - pd.DateOffset(months=1))

    # 1-2. Challenger : calibration conforme sur l'année précédant la fenêtre, puis prévisions de la fenêtre
    clim_eval = F.fit_climatology(panel, before_window)
    forecasts = []
    for h in champion["horizons"]:
        rows = training_rows(panel, h, clim_eval, static, before_window)
        before_calib = rows[rows["target_date"] < calib_start]
        calib = rows[(rows["target_date"] >= calib_start) & (rows["target_date"] < window_start)]
        q = conformal_correction(fit_horizon(champion["models"][h], before_calib, features, critical), calib, features)
        models = fit_horizon(champion["models"][h], rows[rows["target_date"] < window_start], features, critical)
        forecasts.append(predict_rows(models, q, rows[rows["target_date"] >= window_start], features))
    v = V.match(pd.concat(forecasts, ignore_index=True), observed, critical)

    # 3. Notes et comparaison avec le bilan réel du champion, sur les mêmes prévisions
    challenger = {int(h): V.scores(g) for h, g in v.groupby("horizon")}
    normal = {int(h): _normal_scores(g) for h, g in v.groupby("horizon")}
    champion_scores, champ_mae, chall_mae = {}, {}, {}
    if champion_record is not None and len(champion_record):
        rec = champion_record[pd.to_datetime(champion_record["target_month"]) >= window_start]
        key = ["reservoir_id", "issue_month", "horizon"]
        both = rec.merge(v[key + ["abs_err"]], on=key, suffixes=("", "_challenger"))
        for h, g in both.groupby("horizon"):
            champion_scores[int(h)] = V.scores(g)
            champ_mae[int(h)], chall_mae[int(h)] = g["abs_err"].mean(), g["abs_err_challenger"].mean()
    checks = gate(challenger, champion_scores, champ_mae, chall_mae)
    decision = "promote" if checks and all(c["passed"] for c in checks) else "keep"

    # 4. Candidat : tout le panel, correction conforme recalculée sur la fenêtre
    cutoff = _month(last.to_timestamp())
    clim_final = F.fit_climatology(panel, cutoff)
    bundle_models = {}
    for h in champion["horizons"]:
        rows = training_rows(panel, h, clim_final, static, cutoff)
        early = fit_horizon(champion["models"][h], rows[rows["target_date"] < window_start], features, critical)
        q = conformal_correction(early, rows[rows["target_date"] >= window_start], features)
        bundle_models[h] = {**fit_horizon(champion["models"][h], rows, features, critical), "conformal_q": q}

    bundle = {
        **champion,
        "created": datetime.now().isoformat(timespec="seconds"),
        "train_end": cutoff,
        "data_end": cutoff,
        "models": bundle_models,
        "climatology": clim_final,
        "retrained_from": f"{champion.get('version')} ({champion.get('created')})",
        "retraining": {"decision": decision, "window": [_month(window_start), cutoff], "checks": checks,
                       "challenger": challenger, "normal": normal, "champion": champion_scores},
    }
    return Retraining(decision, checks, challenger, normal, champion_scores,
                      (_month(window_start), cutoff), bundle, v)
