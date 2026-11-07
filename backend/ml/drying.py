"""
Prévision du mois d'assèchement (passage sous le niveau critique) en saison sèche.

Question posée par les gestionnaires : « émise à la fin du mois t (octobre à
mars), en quel mois cette retenue passera-t-elle sous le niveau critique, et
tiendra-t-elle jusqu'au retour des pluies (fin juin) ? »

Modèle de survie à temps discret : pour chaque mois k = 1, 2, … après t, on
prévoit le risque h(k) = P(franchit le seuil au mois t+k | pas encore franchi).
La survie S(k) = Π (1 − h(j)), j ≤ k, donne la loi complète du mois
d'assèchement : mois médian, intervalle, probabilité de tenir jusqu'à juin.

Entrée : le panel mensuel du notebook (`data/gee/panel_monthly.parquet`) ou le
même panel lu dans la base (`reservoir_id`, `date`, `fill`, `a_ref_ha`,
`precip_mm`, `pet_mm`).

Règle d'or (comme `ml/features.py`) : une ligne émise au mois t n'utilise que
l'information disponible à la fin du mois t ; les climatologies d'une saison
d'entraînement sont calculées en excluant cette saison.
"""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

THRESHOLD = 0.20                        # niveau critique (part de la surface de référence)
ISSUE_MONTHS = (10, 11, 12, 1, 2, 3)    # mois d'émission : octobre à mars
LAST_STEP = 8                           # fin de la fenêtre : juin (8 mois après octobre)
SURVIVE = LAST_STEP + 1                 # code « tient jusqu'à fin juin »
A_REF_MIN_HA = 2.0                      # mêmes réservoirs modélisables que le notebook

ROW_FEATURES = [
    "fill_l0", "fill_l1", "fill_l2", "dfill_1", "dfill_2", "peak_fill",
    "issue_step", "log_a_ref", "rain_season", "rain_recent", "pet_l0",
    "clim_fill_issue", "anom_issue", "clim_cross", "clim_survive_share",
]
STEP_FEATURES = ["k", "target_step", "clim_fill_target", "projected_fill"]
FEATURES = ROW_FEATURES + STEP_FEATURES


# --------------------------------------------------------------------------- #
# Calendrier hydrologique
# --------------------------------------------------------------------------- #
def season_of(date: pd.Series) -> pd.Series:
    """Année hydrologique : commence en juillet (pic d'août-octobre puis saison sèche)."""
    return date.dt.year.where(date.dt.month >= 7, date.dt.year - 1)


def step_of(month: pd.Series) -> pd.Series:
    """Mois écoulés depuis octobre de la même saison (juillet = −3 … juin = 8)."""
    return (month - 10) % 12 - 12 * (month.isin([7, 8, 9])).astype(int)


def prepare(panel: pd.DataFrame) -> pd.DataFrame:
    """Réservoirs modélisables, saison et pas de temps, tri chronologique."""
    p = panel[panel["a_ref_ha"] >= A_REF_MIN_HA].copy()
    p["date"] = pd.to_datetime(p["date"])
    p["season"] = season_of(p["date"])
    p["step"] = step_of(p["date"].dt.month)
    return p.sort_values(["reservoir_id", "date"]).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Événements et climatologies
# --------------------------------------------------------------------------- #
def season_curves(p: pd.DataFrame) -> pd.DataFrame:
    """Remplissage par (réservoir, saison) et pas de temps −3 … 8 (colonnes)."""
    return p.pivot_table(index=["reservoir_id", "season"], columns="step", values="fill")


def crossing_steps(curves: pd.DataFrame, threshold: float = THRESHOLD) -> pd.Series:
    """Premier pas 0 … 8 (octobre … juin) sous le seuil ; SURVIVE si jamais ; NaN si saison incomplète."""
    dry = curves.reindex(columns=range(0, LAST_STEP + 1))
    complete = dry.notna().all(axis=1)
    below = dry.lt(threshold)
    first = below.to_numpy().argmax(axis=1).astype(float)
    first[~below.any(axis=1).to_numpy()] = SURVIVE
    return pd.Series(first, index=dry.index).where(complete)


def climatology(curves: pd.DataFrame, crossings: pd.Series, ref_seasons: Iterable[int],
                exclude: int | None = None) -> pd.DataFrame:
    """Climatologie par réservoir sur les saisons de référence (hors `exclude`).

    Colonnes : remplissage médian par pas 0 … 8 (`clim_s0` …), pas médian de
    franchissement (`clim_cross`) et part des saisons où le seuil n'a pas été franchi.
    """
    ref = [s for s in ref_seasons if s != exclude]
    seasons = curves.index.get_level_values("season")
    c = curves[seasons.isin(ref)].reindex(columns=range(0, LAST_STEP + 1))
    fill = c.groupby(level="reservoir_id").median()
    fill.columns = [f"clim_s{s}" for s in fill.columns]
    x = crossings[crossings.index.get_level_values("season").isin(ref)].dropna()
    by_res = x.groupby(level="reservoir_id")
    out = fill.join(by_res.median().rename("clim_cross"), how="outer")
    return out.join((x == SURVIVE).groupby(level="reservoir_id").mean().rename("clim_survive_share"))


# --------------------------------------------------------------------------- #
# Lignes d'émission (une par réservoir × saison × mois d'émission)
# --------------------------------------------------------------------------- #
def issue_rows(p: pd.DataFrame, ref_seasons: Iterable[int], threshold: float = THRESHOLD,
               loso: bool = True, only_complete: bool = True) -> pd.DataFrame:
    """Lignes émises d'octobre à mars pour les retenues encore au-dessus du seuil.

    `event_k` = nombre de mois jusqu'au franchissement (1 … K) ou NaN si la retenue
    tient jusqu'à fin juin ; `K` = mois restant jusqu'à fin juin.
    `loso` : pour une saison de référence, climatologie calculée sans elle.
    """
    ref_seasons = list(ref_seasons)
    curves = season_curves(p)
    crossings = crossing_steps(curves, threshold)
    base = climatology(curves, crossings, ref_seasons)
    clim_by_season = {s: climatology(curves, crossings, ref_seasons, exclude=s)
                      for s in ref_seasons} if loso else {}

    g = p.groupby("reservoir_id")
    q = p.assign(
        fill_l1=g["fill"].shift(1), fill_l2=g["fill"].shift(2),
        rain_recent=g["precip_mm"].shift(1) + p["precip_mm"],
    )
    # Pic de la saison jusqu'au mois t (la saison commence en juillet)
    q["peak_fill"] = q.groupby(["reservoir_id", "season"])["fill"].cummax()
    # Pluie de juin à septembre de l'année où commence la saison (juin appartient à la saison précédente)
    rainy = p[p["date"].dt.month.isin([6, 7, 8, 9])]
    jjas = rainy.groupby(["reservoir_id", rainy["date"].dt.year.rename("season")])["precip_mm"].sum(min_count=4)
    rows = q[q["date"].dt.month.isin(ISSUE_MONTHS) & (q["fill"] >= threshold)].copy()
    rows = rows.rename(columns={"fill": "fill_l0", "step": "issue_step", "pet_mm": "pet_l0"})
    rows["K"] = LAST_STEP - rows["issue_step"]
    rows["dfill_1"] = rows["fill_l0"] - rows["fill_l1"]
    rows["dfill_2"] = rows["fill_l0"] - rows["fill_l2"]
    rows["log_a_ref"] = np.log10(rows["a_ref_ha"])
    rows["rain_season"] = jjas.reindex(pd.MultiIndex.from_frame(rows[["reservoir_id", "season"]])).to_numpy()

    # Observation : premier mois après t sous le seuil, dans la fenêtre
    cur = curves.reindex(pd.MultiIndex.from_frame(rows[["reservoir_id", "season"]]))
    steps = np.arange(1, LAST_STEP + 1)
    future = np.full((len(rows), LAST_STEP), np.nan)
    for i, s0 in enumerate(rows["issue_step"].to_numpy()):
        cols = [s for s in s0 + steps if s <= LAST_STEP]
        future[i, :len(cols)] = cur.iloc[i].reindex(cols).to_numpy()
    k_max = rows["K"].to_numpy()
    observed = np.array([np.isfinite(future[i, :k]).all() for i, k in enumerate(k_max)])
    below = np.nan_to_num(future, nan=np.inf) < threshold
    first = np.where(below.any(axis=1), below.argmax(axis=1) + 1.0, np.nan)
    rows["event_k"] = np.where(first <= k_max, first, np.nan)
    rows["complete"] = observed

    # Climatologies (sans la saison de la ligne si elle sert de référence)
    clim = pd.concat([
        (clim_by_season.get(s, base)).reindex(grp["reservoir_id"]).set_index(grp.index)
        for s, grp in rows.groupby("season")
    ]).reindex(rows.index)
    rows = rows.join(clim)
    issue_cols = [f"clim_s{s}" for s in rows["issue_step"]]
    rows["clim_fill_issue"] = [rows.at[i, c] for i, c in zip(rows.index, issue_cols)]
    rows["anom_issue"] = rows["fill_l0"] - rows["clim_fill_issue"]
    if only_complete:
        rows = rows[rows["complete"]]
    return rows.reset_index(drop=True)


def person_period(rows: pd.DataFrame, full: bool = False) -> pd.DataFrame:
    """Une ligne par mois à risque. `full` : tous les mois jusqu'à juin (prévision)."""
    k_end = rows["K"] if full else rows["event_k"].fillna(rows["K"])
    idx = np.repeat(rows.index.to_numpy(), k_end.astype(int).to_numpy())
    pp = rows.loc[idx].reset_index().rename(columns={"index": "row"})
    pp["k"] = pp.groupby("row").cumcount() + 1
    pp["target_step"] = pp["issue_step"] + pp["k"]
    pp["clim_fill_target"] = [pp.at[i, f"clim_s{s}"] for i, s in zip(pp.index, pp["target_step"])]
    # Projection : l'écart à la normale observé en t se maintient
    pp["projected_fill"] = pp["fill_l0"] + pp["clim_fill_target"] - pp["clim_fill_issue"]
    pp["y"] = (pp["k"] == pp["event_k"]).astype(int)
    return pp


# --------------------------------------------------------------------------- #
# Loi du mois d'assèchement
# --------------------------------------------------------------------------- #
def survival(hazard: np.ndarray, pp: pd.DataFrame, n_rows: int) -> np.ndarray:
    """Probabilités P(franchit au mois k), k = 1 … 8, et P(tient) en dernière colonne."""
    h = np.zeros((n_rows, LAST_STEP))
    h[pp["row"].to_numpy(), pp["k"].to_numpy() - 1] = hazard
    s = np.cumprod(1 - h, axis=1)
    s_prev = np.hstack([np.ones((n_rows, 1)), s[:, :-1]])
    dist = np.hstack([s_prev * h, s[:, -1:]])
    return dist


def predict_distribution(model, rows: pd.DataFrame) -> np.ndarray:
    """Loi du mois de franchissement pour chaque ligne (somme = 1 sur K mois + « tient »)."""
    rows = rows.reset_index(drop=True)
    pp = person_period(rows, full=True)
    hazard = model.predict_proba(pp[FEATURES])[:, 1]
    dist = survival(hazard, pp, len(rows))
    # les mois au-delà de K n'existent pas : la survie à K est « tient jusqu'à juin »
    for i, k in enumerate(rows["K"].astype(int)):
        dist[i, LAST_STEP] = 1 - dist[i, :k].sum()
        dist[i, k:LAST_STEP] = 0
    return dist


def summarise(dist: np.ndarray, rows: pd.DataFrame, levels=(0.1, 0.5, 0.9)) -> pd.DataFrame:
    """Quantiles du mois de franchissement (en mois après t ; K+1 = tient jusqu'à juin)."""
    rows = rows.reset_index(drop=True)
    cdf = np.cumsum(dist, axis=1)
    out = {}
    for q in levels:
        k = (cdf >= q - 1e-9).argmax(axis=1) + 1.0
        out[f"k_q{int(q * 100)}"] = np.minimum(k, rows["K"].to_numpy() + 1)
    out["p_survive"] = dist[:, LAST_STEP]
    return pd.DataFrame(out)


def observed_k(rows: pd.DataFrame) -> np.ndarray:
    """Mois de franchissement observé, K+1 si la retenue a tenu jusqu'à juin."""
    return rows["event_k"].fillna(rows["K"] + 1).to_numpy()


def forecast_drying(model, panel: pd.DataFrame, issue: str | pd.Timestamp, ref_seasons: Iterable[int],
                    threshold: float = THRESHOLD) -> pd.DataFrame:
    """Bulletin émis à la fin du mois `issue` (octobre à mars) : une ligne par retenue encore au-dessus du seuil.

    Mois probable de passage sous le seuil, intervalle à 80 % et probabilité de tenir jusqu'à fin juin.
    Les retenues déjà sous le seuil en `issue` ne figurent pas : elles sont déjà critiques.
    """
    issue = pd.Timestamp(issue).to_period("M").to_timestamp()
    if issue.month not in ISSUE_MONTHS:
        raise ValueError(f"mois d'émission {issue:%Y-%m} hors saison sèche (octobre à mars)")
    rows = issue_rows(prepare(panel), ref_seasons, threshold, loso=False, only_complete=False)
    rows = rows[rows["date"] == issue].reset_index(drop=True)
    q = summarise(predict_distribution(model, rows), rows)

    def label(k, K):
        return "after June" if k > K else f"{issue + pd.DateOffset(months=int(k)):%Y-%m}"

    return pd.DataFrame({
        "reservoir_id": rows["reservoir_id"],
        "issue_month": f"{issue:%Y-%m}",
        "fill_now": rows["fill_l0"].round(3),
        "critical_month": [label(k, K) for k, K in zip(q["k_q50"], rows["K"])],
        "earliest_80": [label(k, K) for k, K in zip(q["k_q10"], rows["K"])],
        "latest_80": [label(k, K) for k, K in zip(q["k_q90"], rows["K"])],
        "p_lasts_to_june": q["p_survive"].round(3),
        "usual_month": [label(k, K) for k, K in zip(baseline_climatology(rows), rows["K"])],
    }).sort_values(["critical_month", "p_lasts_to_june"]).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Références (baselines)
# --------------------------------------------------------------------------- #
def baseline_climatology(rows: pd.DataFrame) -> np.ndarray:
    """Le mois habituel de franchissement du réservoir (au plus tôt le mois suivant)."""
    k = rows["clim_cross"].fillna(SURVIVE) - rows["issue_step"]
    return np.clip(np.round(k), 1, rows["K"] + 1).to_numpy()


def baseline_kaplan_meier(train_rows: pd.DataFrame, rows: pd.DataFrame) -> np.ndarray:
    """Loi de référence : survie empirique de tous les réservoirs, par mois d'émission (Kaplan-Meier).

    Sans censure aléatoire (la fenêtre s'arrête en juin pour tous), c'est la
    fréquence observée des mois de franchissement sur les saisons d'entraînement.
    """
    rows = rows.reset_index(drop=True)
    dist = np.zeros((len(rows), LAST_STEP + 1))
    for step, grp in rows.groupby("issue_step"):
        ref = train_rows[train_rows["issue_step"] == step]
        k_obs = observed_k(ref).astype(int)
        freq = np.bincount(k_obs, minlength=LAST_STEP + 2)[1:].astype(float)
        freq = (freq + 0.5) / (freq.sum() + 0.5 * len(freq))      # lissage : aucune probabilité nulle
        K = LAST_STEP - int(step)
        d = np.zeros(LAST_STEP + 1)
        d[:K] = freq[:K]
        d[LAST_STEP] = freq[K]
        dist[grp.index] = d / d.sum()
    return dist


def baseline_projection(rows: pd.DataFrame, threshold: float = THRESHOLD) -> np.ndarray:
    """Décrue climatologique décalée de l'anomalie actuelle : premier mois projeté sous le seuil."""
    pp = person_period(rows.reset_index(drop=True), full=True)
    hit = pp[pp["projected_fill"] < threshold].groupby("row")["k"].min()
    k = hit.reindex(range(len(rows)))
    return k.fillna(rows["K"].reset_index(drop=True) + 1).to_numpy()


def baseline_trend(rows: pd.DataFrame, threshold: float = THRESHOLD) -> np.ndarray:
    """Extrapolation linéaire de la baisse du dernier mois (règle empirique de terrain)."""
    rate = (-rows["dfill_1"]).clip(lower=1e-6)
    k = np.ceil((rows["fill_l0"] - threshold) / rate).clip(lower=1)
    k = k.where(rows["dfill_1"] < 0, rows["K"] + 1)
    return np.minimum(k, rows["K"] + 1).to_numpy()


# --------------------------------------------------------------------------- #
# Évaluation
# --------------------------------------------------------------------------- #
def point_metrics(pred_k: np.ndarray, rows: pd.DataFrame) -> dict:
    """Erreur en mois sur le mois de franchissement (« tient » codé K+1)."""
    obs = observed_k(rows)
    err = np.abs(np.asarray(pred_k, dtype=float) - obs)
    survived = rows["event_k"].isna().to_numpy()
    pred_survive = np.asarray(pred_k) == (rows["K"].to_numpy() + 1)
    return {
        "MAE_months": err.mean(),
        "within_1_month": (err <= 1).mean(),
        "exact_month": (err == 0).mean(),
        "survive_accuracy": (pred_survive == survived).mean(),
    }


def concordance(pred_k: np.ndarray, rows: pd.DataFrame) -> float:
    """Indice C de Harrell par mois d'émission (classement des urgences), moyenne pondérée."""
    obs, event = observed_k(rows), rows["event_k"].notna().to_numpy()
    pred = np.asarray(pred_k, dtype=float)
    num = den = 0.0
    for _, idx in rows.reset_index(drop=True).groupby(["season", "issue_step"]).indices.items():
        o, e, p = obs[idx], event[idx], pred[idx]
        earlier = (o[:, None] < o[None, :]) & e[:, None]
        num += ((p[:, None] < p[None, :]) & earlier).sum() + 0.5 * ((p[:, None] == p[None, :]) & earlier).sum()
        den += earlier.sum()
    return num / den if den else np.nan


def distribution_metrics(dist: np.ndarray, rows: pd.DataFrame) -> dict:
    """Score logarithmique, Brier « tient jusqu'à juin », couverture de l'intervalle 80 %."""
    rows = rows.reset_index(drop=True)
    obs = observed_k(rows).astype(int)
    k = rows["K"].to_numpy()
    col = np.where(obs == k + 1, LAST_STEP, obs - 1)
    p_obs = dist[np.arange(len(rows)), col]
    q = summarise(dist, rows)
    survived = rows["event_k"].isna().to_numpy().astype(float)
    return {
        "log_score": np.log(np.clip(p_obs, 1e-6, 1)).mean(),
        "brier_survive": np.mean((q["p_survive"].to_numpy() - survived) ** 2),
        "coverage_80": ((obs >= q["k_q10"]) & (obs <= q["k_q90"])).mean(),
        "width_80_months": (q["k_q90"] - q["k_q10"]).mean(),
    }
