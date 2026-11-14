"""
Prélèvements anormaux : retenues qui baissent plus vite que prévu en saison sèche.

Question posée par les gestionnaires : « quelles retenues perdent leur eau
nettement plus vite que ce que l'évaporation et leur comportement habituel
expliquent ? »

Principe :
  1. Baisse mensuelle observée, exprimée en indice de niveau (mm) : la surface
     est convertie en hauteur d'eau équivalente par la relation de Liebe et al.
     (2005), V = k · A^b, d'où h = k · b / (b − 1) · A^(b − 1).
  2. Baisse attendue : un modèle appris sur les AUTRES retenues (évaporation
     potentielle, mois, remplissage, taille). Une retenue ne sert jamais à
     calculer sa propre référence.
  3. Écart = baisse observée − baisse attendue, puis deux lectures :
       - chronique : la retenue baisse durablement plus vite que ses semblables ;
       - épisodique : une saison, elle baisse plus vite que d'habitude.

Limites à garder en tête :
  - L'indice de niveau dépend d'une forme de cuvette moyenne. Il sert à comparer
    des retenues et des saisons, pas à mesurer des millimètres réels.
  - Un écart signale une perte inexpliquée (prélèvement, infiltration, brèche,
    erreur de mesure). Sans donnée de terrain, ce n'est pas une preuve de
    prélèvement : le résultat est une liste de retenues à vérifier.
  - Un mois où la retenue se vide entièrement est ignoré (la baisse réelle est
    inconnue : elle vaut au moins le niveau restant).

Entrée : le panel mensuel (`data/gee/panel_monthly.parquet`) ou le même panel lu
dans la base (`reservoir_id`, `date`, `area_ha`, `fill`, `a_ref_ha`,
`precip_mm`, `pet_mm`, et si disponibles `area_source`, `outlier`).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

from ml.drying import prepare

# Relation de Liebe : mêmes constantes que `app/collectors/water_area.py`
LIEBE_K, LIEBE_EXP = 0.00857, 1.4367
_LEVEL_COEF = LIEBE_K * LIEBE_EXP / (LIEBE_EXP - 1)     # h (m) = coef · A(m²)^(b − 1)

START_MONTHS = (11, 12, 1, 2, 3)   # mois de départ d'une baisse mensuelle (novembre → avril)
RAIN_MAX_MM = 10.0                 # au-delà, des apports sont possibles : mois écarté
FILL_MIN = 0.10                    # en dessous, la surface est trop petite pour être fiable
AREA_MIN_HA = 1.0
MIN_MONTHS_CHRONIC = 6             # mois valides pour juger une retenue sur la durée
MIN_MONTHS_SEASON = 2              # mois valides pour juger une saison
MIN_MONTHS_HISTORY = 4             # mois des autres saisons pour établir l'habitude
Z_CHRONIC = 2.5
Z_EPISODIC = 3.0

FEATURES = ["pet_mm_mean", "step", "fill", "level_mm", "log_a_ref", "peak_fill"]


# --------------------------------------------------------------------------- #
# Indice de niveau
# --------------------------------------------------------------------------- #
def level_mm(area_ha) -> np.ndarray:
    """Hauteur d'eau équivalente (mm) d'une surface en eau (ha), selon Liebe."""
    area_m2 = np.clip(np.asarray(area_ha, dtype=float), 0, None) * 1e4
    return _LEVEL_COEF * area_m2 ** (LIEBE_EXP - 1) * 1000


def area_from_level(level) -> np.ndarray:
    """Réciproque de `level_mm` : surface (ha) pour un indice de niveau (mm)."""
    h_m = np.clip(np.asarray(level, dtype=float), 0, None) / 1000
    return (h_m / _LEVEL_COEF) ** (1 / (LIEBE_EXP - 1)) / 1e4


# --------------------------------------------------------------------------- #
# Baisses mensuelles de saison sèche
# --------------------------------------------------------------------------- #
def monthly_drops(panel: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par (retenue, mois t) : baisse de l'indice de niveau entre t et t+1.

    Ne garde que les mois de saison sèche sans pluie, mesurés par Sentinel-2 aux
    deux dates, hors valeurs aberrantes, avec une surface de départ suffisante.
    `censored` : la retenue est vide en t+1 (baisse réelle inconnue).
    """
    p = prepare(panel)
    if "area_source" not in p:
        p["area_source"] = "S2"
    if "outlier" not in p:
        p["outlier"] = False
    p["level_mm"] = level_mm(p["area_ha"])
    p["peak_fill"] = p.groupby(["reservoir_id", "season"])["fill"].cummax()
    g = p.groupby("reservoir_id")
    nxt = {c: g[c].shift(-1) for c in ["date", "level_mm", "area_ha", "precip_mm", "pet_mm", "area_source", "outlier"]}

    consecutive = nxt["date"] == p["date"] + pd.DateOffset(months=1)
    measured = (p["area_source"] == "S2") & (nxt["area_source"] == "S2")
    clean = ~p["outlier"].astype(bool) & ~nxt["outlier"].fillna(True).astype(bool)
    dry = (p["precip_mm"] < RAIN_MAX_MM) & (nxt["precip_mm"] < RAIN_MAX_MM)
    wet_enough = (p["fill"] >= FILL_MIN) & (p["area_ha"] >= AREA_MIN_HA)
    keep = consecutive & measured & clean & dry & wet_enough & p["date"].dt.month.isin(START_MONTHS)

    d = p.loc[keep, ["reservoir_id", "date", "season", "step", "fill", "area_ha", "a_ref_ha", "level_mm", "peak_fill"]].copy()
    d["drop_mm"] = d["level_mm"] - nxt["level_mm"][keep]
    d["pet_mm_mean"] = (p.loc[keep, "pet_mm"] + nxt["pet_mm"][keep]) / 2
    d["log_a_ref"] = np.log10(d["a_ref_ha"])
    d["censored"] = nxt["area_ha"][keep] <= 0
    return d.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Baisse attendue : modèle appris sur les autres retenues
# --------------------------------------------------------------------------- #
class PeerModel:
    """Baisse attendue d'une retenue, prévue par des modèles qui ne l'ont jamais vue.

    Les retenues sont réparties en `n_splits` groupes ; chaque modèle est entraîné
    sans un groupe et sert à prévoir ce groupe. Une retenue inconnue reçoit la
    moyenne des modèles.
    """

    def __init__(self, n_splits: int = 5, random_state: int = 0):
        self.n_splits = n_splits
        self.random_state = random_state
        self.models_: list[HistGradientBoostingRegressor] = []
        self.fold_of_: dict[str, int] = {}

    def _new_model(self) -> HistGradientBoostingRegressor:
        # Erreur absolue : la médiane conditionnelle résiste aux mois aberrants
        # (y compris aux prélèvements que l'on cherche justement à repérer).
        return HistGradientBoostingRegressor(loss="absolute_error", max_iter=200, learning_rate=0.05,
                                             max_depth=3, random_state=self.random_state)

    def fit(self, drops: pd.DataFrame) -> "PeerModel":
        train = drops[~drops["censored"]].reset_index(drop=True)
        groups = train["reservoir_id"].to_numpy()
        n_splits = min(self.n_splits, len(np.unique(groups)))
        if n_splits < 2:
            raise ValueError("il faut au moins deux retenues pour établir une baisse attendue")
        self.models_, self.fold_of_ = [], {}
        for fold, (tr, te) in enumerate(GroupKFold(n_splits).split(train, groups=groups)):
            self.models_.append(self._new_model().fit(train.loc[tr, FEATURES], train.loc[tr, "drop_mm"]))
            self.fold_of_.update({rid: fold for rid in np.unique(groups[te])})
        return self

    def predict(self, drops: pd.DataFrame) -> np.ndarray:
        preds = np.column_stack([m.predict(drops[FEATURES]) for m in self.models_])
        fold = drops["reservoir_id"].map(self.fold_of_)
        own = preds[np.arange(len(drops)), fold.fillna(0).astype(int).to_numpy()]
        return np.where(fold.notna().to_numpy(), own, preds.mean(axis=1))


def add_excess(drops: pd.DataFrame, model: PeerModel) -> pd.DataFrame:
    """Ajoute la baisse attendue et l'écart (observé − attendu), en mm d'indice de niveau."""
    out = drops.copy()
    out["expected_mm"] = model.predict(out)
    out["excess_mm"] = out["drop_mm"] - out["expected_mm"]
    return out


# --------------------------------------------------------------------------- #
# Détection des écarts
# --------------------------------------------------------------------------- #
def robust_sd(x) -> float:
    """Écart-type robuste (1,4826 × écart absolu médian)."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return float(1.4826 * np.median(np.abs(x - np.median(x)))) if len(x) else np.nan


def chronic(scored: pd.DataFrame, z_min: float = Z_CHRONIC) -> pd.DataFrame:
    """Retenues qui baissent durablement plus vite que leurs semblables.

    Une ligne par retenue ayant assez de mois valides : écart médian, rapport
    observé / attendu, et score z par rapport à l'ensemble des retenues.
    """
    s = scored[~scored["censored"]]
    by = s.groupby("reservoir_id")
    out = pd.DataFrame({
        "n_months": by.size(),
        "a_ref_ha": by["a_ref_ha"].first(),
        "drop_mm": by["drop_mm"].median(),
        "expected_mm": by["expected_mm"].median(),
        "excess_mm": by["excess_mm"].median(),
    })
    out = out[out["n_months"] >= MIN_MONTHS_CHRONIC]
    out["ratio"] = out["drop_mm"] / out["expected_mm"]
    out["z"] = (out["excess_mm"] - out["excess_mm"].median()) / robust_sd(out["excess_mm"])
    out["flag"] = out["z"] >= z_min
    return out.sort_values("z", ascending=False).reset_index()


def deviation_scale(seasons: pd.DataFrame) -> pd.Series:
    """Dispersion habituelle de l'écart saisonnier, selon le nombre de mois valides.

    Écart-type robuste sur toutes les (retenue, saison) ayant le même nombre de
    mois ; s'il y en a moins de 20, la dispersion tous effectifs confondus.
    L'entrée -1 de la série donne cette dispersion générale.
    """
    overall = robust_sd(seasons["deviation_mm"])
    by_n = seasons.groupby("n_months")["deviation_mm"].agg([robust_sd, "size"])
    scale = by_n["robust_sd"].where(by_n["size"] >= 20, overall)
    scale.loc[-1] = overall
    return scale


def episodic(scored: pd.DataFrame, z_min: float = Z_EPISODIC, scale: pd.Series | None = None) -> pd.DataFrame:
    """Saisons où une retenue baisse plus vite que d'habitude.

    Pour chaque (retenue, saison) : écart moyen de la saison, comparé à l'écart
    habituel de la même retenue les AUTRES saisons, au même mois quand il y a
    assez de recul (sinon tous mois confondus). Le score z rapporte cette
    différence à sa dispersion sur l'ensemble des retenues et des saisons
    (`deviation_scale`). `scale` : dispersion de référence à réutiliser, par
    exemple pour noter une retenue isolée ou un panel modifié.
    """
    s = scored[~scored["censored"]]
    rows = []
    for rid, grp in s.groupby("reservoir_id"):
        for season, cur in grp.groupby("season"):
            other = grp[grp["season"] != season]
            if len(cur) < MIN_MONTHS_SEASON or len(other) < MIN_MONTHS_HISTORY:
                continue
            overall = other["excess_mm"].median()
            by_step = other.groupby("step")["excess_mm"].agg(["median", "size"])
            usual_by_step = by_step["median"].where(by_step["size"] >= 3)
            usual = cur["step"].map(usual_by_step).fillna(overall)
            rows.append({
                "reservoir_id": rid, "season": season, "n_months": len(cur),
                "excess_mm": cur["excess_mm"].mean(), "usual_excess_mm": usual.mean(),
                "drop_mm": cur["drop_mm"].mean(), "expected_mm": cur["expected_mm"].mean(),
            })
    out = pd.DataFrame(rows, columns=["reservoir_id", "season", "n_months", "excess_mm", "usual_excess_mm",
                                      "drop_mm", "expected_mm"])
    out["deviation_mm"] = out["excess_mm"] - out["usual_excess_mm"]
    if out.empty:
        return out.assign(z=np.nan, flag=False)
    if scale is None:
        scale = deviation_scale(out)
    out["z"] = out["deviation_mm"] / out["n_months"].map(scale).fillna(scale.loc[-1])
    out["flag"] = out["z"] >= z_min
    return out.sort_values("z", ascending=False).reset_index(drop=True)


def detect(panel: pd.DataFrame, model: PeerModel | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Chaîne complète : (baisses mensuelles avec écarts, lecture chronique, lecture épisodique)."""
    drops = monthly_drops(panel)
    model = model or PeerModel().fit(drops)
    scored = add_excess(drops, model)
    return scored, chronic(scored), episodic(scored)


# --------------------------------------------------------------------------- #
# Validation par injection de prélèvements fictifs
# --------------------------------------------------------------------------- #
def inject_withdrawal(panel: pd.DataFrame, reservoir_id: str, season: int, extra_mm: float) -> pd.DataFrame:
    """Copie du panel où la retenue perd `extra_mm` d'indice de niveau de plus par mois.

    Le prélèvement fictif commence en novembre de la saison et se cumule jusqu'en
    juin ; surface et remplissage sont recalculés à partir du niveau abaissé.
    """
    out = panel.copy()
    dates = pd.to_datetime(out["date"])
    start = pd.Timestamp(year=season, month=11, day=1)
    end = pd.Timestamp(year=season + 1, month=6, day=1)
    hit = (out["reservoir_id"] == reservoir_id) & (dates >= start) & (dates <= end)
    months = (dates[hit].dt.year - start.year) * 12 + dates[hit].dt.month - start.month + 1
    lowered = level_mm(out.loc[hit, "area_ha"]) - extra_mm * months.to_numpy()
    area = area_from_level(lowered)
    out.loc[hit, "area_ha"] = area
    out.loc[hit, "fill"] = area / out.loc[hit, "a_ref_ha"]
    return out
