"""
Variables explicatives du modèle de prévision du taux de remplissage (v3).

Source unique de vérité partagée par :
  - le notebook `notebooks/WaterTracker_pipeline.ipynb` (entraînement) ;
  - le service d'inférence de l'API.

Entrée : un panel mensuel complet (une ligne par réservoir × mois) contenant au
minimum `reservoir_id`, `date` (1er du mois), `fill` (taux de remplissage),
`area_source` et les forçages climatiques du sous-bassin (`precip_mm`, `pet_mm`,
`aet_mm`, `t2m_c`, `soil_moist`).

Règle d'or : chaque variable de la ligne émise au mois t n'utilise que de
l'information disponible à la fin du mois t (aucune donnée future).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FILL_LAGS = (0, 1, 2, 3, 12)
CLIMATE_COLS = ("precip_mm", "pet_mm", "aet_mm", "t2m_c", "soil_moist")
STATIC_COLS = (
    "log_a_ref", "jrc_occ_mean", "jrc_seasonality", "elev_m", "slope_deg",
    "log_basin_km2", "log_upstream_km2", "log_catchment_ratio",
)

FEATURES = [
    # état du réservoir et dynamique récente
    *[f"fill_l{k}" for k in FILL_LAGS], "dfill_1", "dfill_3",
    # climatologie propre au réservoir
    "clim_issue", "clim_target", "anom_issue",
    # forçages climatiques passés
    "precip_mm", "precip_3m", "precip_6m", "precip_3m_anom",
    "pet_mm", "aet_mm", "t2m_c", "soil_moist",
    "clim_precip_target",
    # calendrier
    "target_month_sin", "target_month_cos", "issue_month_sin", "issue_month_cos",
    # caractéristiques physiques
    *STATIC_COLS,
    # qualité de l'observation courante
    "is_s2",
]


# --------------------------------------------------------------------------- #
# Statistiques apprises sur la période d'entraînement
# --------------------------------------------------------------------------- #
def static_features(reservoirs: pd.DataFrame) -> pd.DataFrame:
    """Caractéristiques physiques (une ligne par réservoir, index reservoir_id)."""
    r = reservoirs.set_index("reservoir_id")
    out = pd.DataFrame(index=r.index)
    out["log_a_ref"] = np.log10(r["a_ref_ha"])
    out["jrc_occ_mean"] = r["jrc_occ_mean"]
    out["jrc_seasonality"] = r["jrc_seasonality"]
    out["elev_m"] = r["elev_m"]
    out["slope_deg"] = r["slope_deg"]
    out["log_basin_km2"] = np.log10(r["basin_km2"])
    out["log_upstream_km2"] = np.log10(r["upstream_km2"])
    # Rapport bassin / plan d'eau : capacité du bassin à remplir le réservoir
    out["log_catchment_ratio"] = np.log10(r["basin_km2"] * 100 / r["a_ref_ha"])
    return out


def add_precip_windows(panel: pd.DataFrame) -> pd.DataFrame:
    """Cumuls de pluie glissants (mois courant inclus)."""
    p = panel.sort_values(["reservoir_id", "date"]).copy()
    g = p.groupby("reservoir_id")["precip_mm"]
    p["precip_3m"] = g.transform(lambda s: s.rolling(3, min_periods=3).sum())
    p["precip_6m"] = g.transform(lambda s: s.rolling(6, min_periods=6).sum())
    return p


def fit_climatology(panel: pd.DataFrame, train_end: str) -> dict[str, pd.DataFrame]:
    """Climatologies (médianes par réservoir et mois calendaire) sur l'entraînement.

    Retourne aussi la version « leave-one-year-out » utilisée pour les lignes
    d'entraînement : la climatologie d'un mois n'inclut jamais la valeur de la
    même année (sinon la cible fuirait dans la variable `clim_target`).
    """
    p = add_precip_windows(panel)
    p = p[p["date"] <= pd.Period(train_end, "M").to_timestamp()].copy()
    p["cal_month"] = p["date"].dt.month
    p["year"] = p["date"].dt.year

    fill = p.groupby(["reservoir_id", "cal_month"])["fill"].median().rename("clim_fill")
    precip = p.groupby(["reservoir_id", "cal_month"])["precip_mm"].mean().rename("clim_precip")
    precip3 = p.groupby(["reservoir_id", "cal_month"])["precip_3m"].mean().rename("clim_precip_3m")

    rows = []
    for (rid, m), grp in p.groupby(["reservoir_id", "cal_month"]):
        vals = grp.set_index("year")["fill"]
        for y in vals.index:
            rows.append((rid, m, y, vals.drop(y).median()))
    loyo = pd.DataFrame(rows, columns=["reservoir_id", "cal_month", "year", "clim_fill_loyo"])
    return {
        "monthly": pd.concat([fill, precip, precip3], axis=1).reset_index(),
        "loyo": loyo,
    }


# --------------------------------------------------------------------------- #
# Construction des lignes (réservoir, mois d'émission t, horizon h)
# --------------------------------------------------------------------------- #
def _month_cyc(month: pd.Series, prefix: str) -> pd.DataFrame:
    angle = 2 * np.pi * (month - 1) / 12
    return pd.DataFrame({f"{prefix}_sin": np.sin(angle), f"{prefix}_cos": np.cos(angle)}, index=month.index)


def build_rows(
    panel: pd.DataFrame,
    horizon: int,
    climatology: dict[str, pd.DataFrame],
    static: pd.DataFrame,
    train_end: str | None = None,
    with_target: bool = True,
) -> pd.DataFrame:
    """Une ligne par (réservoir, mois d'émission t) pour l'horizon h.

    `train_end` : les lignes dont le mois cible est <= train_end reçoivent la
    climatologie leave-one-year-out (pas de fuite de la cible).
    """
    p = add_precip_windows(panel)
    p["cal_month"] = p["date"].dt.month
    g = p.groupby("reservoir_id")

    for k in FILL_LAGS:
        p[f"fill_l{k}"] = g["fill"].shift(k)
    p["dfill_1"] = p["fill_l0"] - p["fill_l1"]
    p["dfill_3"] = p["fill_l0"] - p["fill_l3"]
    p["is_s2"] = (p["area_source"] == "S2").astype(float)

    p["target_date"] = p["date"] + pd.DateOffset(months=horizon)
    p["target_month"] = p["target_date"].dt.month
    if with_target:
        p["y"] = g["fill"].shift(-horizon)
        # valeur de l'an passé pour le même mois cible (référence « saison naïve »)
        p["fill_target_lastyear"] = g["fill"].shift(12 - horizon)

    clim = climatology["monthly"]
    p = p.merge(
        clim.rename(columns={"clim_fill": "clim_issue", "clim_precip_3m": "_cp3"})
        [["reservoir_id", "cal_month", "clim_issue", "_cp3"]],
        on=["reservoir_id", "cal_month"], how="left",
    )
    p = p.merge(
        clim.rename(columns={"cal_month": "target_month", "clim_fill": "clim_target", "clim_precip": "clim_precip_target"})
        [["reservoir_id", "target_month", "clim_target", "clim_precip_target"]],
        on=["reservoir_id", "target_month"], how="left",
    )

    if train_end is not None:
        loyo = climatology["loyo"].rename(columns={"cal_month": "target_month", "year": "target_year"})
        p["target_year"] = p["target_date"].dt.year
        p = p.merge(loyo, on=["reservoir_id", "target_month", "target_year"], how="left")
        in_train = p["target_date"] <= pd.Period(train_end, "M").to_timestamp()
        p.loc[in_train, "clim_target"] = p.loc[in_train, "clim_fill_loyo"]
        p = p.drop(columns=["clim_fill_loyo", "target_year"])

    p["anom_issue"] = p["fill_l0"] - p["clim_issue"]
    p["precip_3m_anom"] = p["precip_3m"] - p.pop("_cp3")
    p = p.join(_month_cyc(p["target_month"], "target_month")).join(_month_cyc(p["cal_month"], "issue_month"))
    p = p.join(static, on="reservoir_id")
    p["horizon"] = horizon
    return p
