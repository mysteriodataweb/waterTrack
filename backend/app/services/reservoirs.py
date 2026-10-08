"""Accès aux données v3 (réservoirs, surfaces mensuelles, prévisions) et bulletin mensuel."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..config import settings
from ..models import FillForecast, Reservoir, ReservoirSource, WaterAreaObservation, WaterSource

logger = logging.getLogger(__name__)

PANEL_COLUMNS = ["area_ha", "fill", "area_source", "valid_frac", "volume_m3",
                 "precip_mm", "pet_mm", "aet_mm", "t2m_c", "soil_moist"]


def _none(value):
    """Valeur pandas/numpy -> valeur Python pour SQL (NaN -> None ; le pilote pg8000 refuse les types numpy)."""
    if value is None or value is pd.NA:
        return None
    if hasattr(value, "item"):
        value = value.item()
    return None if isinstance(value, float) and np.isnan(value) else value


def _month_start(value) -> date:
    return pd.Timestamp(value).to_period("M").to_timestamp().date()


# --------------------------------------------------------------------------- #
# Lecture
# --------------------------------------------------------------------------- #
def load_panel(db: Session, modelable_only: bool = True) -> pd.DataFrame:
    """Panel mensuel complet (réservoir × mois), mois manquants explicités en NaN.

    Les variables du modèle sont des décalages temporels : un mois absent de la
    base doit apparaître comme une ligne vide, sinon les décalages se décaleraient.
    """
    query = select(WaterAreaObservation.reservoir_id, WaterAreaObservation.month,
                   *[getattr(WaterAreaObservation, c) for c in PANEL_COLUMNS])
    if modelable_only:
        query = query.join(Reservoir).where(Reservoir.modelable.is_(True))
    df = pd.DataFrame(db.execute(query).all(), columns=["reservoir_id", "date", *PANEL_COLUMNS])
    if df.empty:
        return df
    return complete_grid(df)


def complete_grid(df: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par réservoir et par mois entre le premier et le dernier mois observés."""
    df = df.assign(date=pd.to_datetime(df["date"]))
    grid = pd.MultiIndex.from_product(
        [df["reservoir_id"].unique(), pd.date_range(df["date"].min(), df["date"].max(), freq="MS")],
        names=["reservoir_id", "date"],
    )
    df = df.set_index(["reservoir_id", "date"]).reindex(grid).reset_index()
    df["area_source"] = df["area_source"].fillna("manquant")
    return df.sort_values(["reservoir_id", "date"]).reset_index(drop=True)


def latest_issue_month(db: Session) -> Optional[date]:
    return db.execute(select(func.max(FillForecast.issue_month))).scalar()


def forecasts_frame(db: Session, issue_month: Optional[date] = None) -> pd.DataFrame:
    issue_month = issue_month or latest_issue_month(db)
    if issue_month is None:
        return pd.DataFrame()
    rows = db.execute(select(FillForecast).where(FillForecast.issue_month == issue_month)).scalars().all()
    return pd.DataFrame([{c.name: getattr(r, c.name) for c in FillForecast.__table__.columns} for r in rows])


def reservoir_of_source(db: Session, source_id: int) -> Optional[str]:
    return db.execute(
        select(ReservoirSource.reservoir_id).where(ReservoirSource.source_id == source_id)
    ).scalar()


# --------------------------------------------------------------------------- #
# Écriture (upserts idempotents)
# --------------------------------------------------------------------------- #
def upsert_observations(db: Session, df: pd.DataFrame) -> int:
    rows = [
        {"reservoir_id": r.reservoir_id, "month": _month_start(r.month),
         **{c: _none(getattr(r, c)) for c in PANEL_COLUMNS if hasattr(r, c)}}
        for r in df.itertuples(index=False)
    ]
    if not rows:
        return 0
    stmt = insert(WaterAreaObservation).values(rows)
    update_cols = {c: stmt.excluded[c] for c in PANEL_COLUMNS if c in rows[0]}
    db.execute(stmt.on_conflict_do_update(constraint="uq_area_reservoir_month", set_=update_cols))
    return len(rows)


def upsert_forecasts(db: Session, fc: pd.DataFrame, model_version: Optional[str]) -> int:
    cols = ["fill_now", "fill_pred", "fill_lo80", "fill_hi80", "p_critical", "status"]
    rows = [
        {"reservoir_id": r.reservoir_id, "issue_month": _month_start(r.issue_month), "horizon": int(r.horizon),
         "target_month": _month_start(r.target_month), "model_version": model_version,
         **{c: float(getattr(r, c)) if c != "status" else r.status for c in cols}}
        for r in fc.itertuples(index=False)
    ]
    if not rows:
        return 0
    stmt = insert(FillForecast).values(rows)
    db.execute(stmt.on_conflict_do_update(
        constraint="uq_forecast",
        set_={c: stmt.excluded[c] for c in [*cols, "target_month", "model_version"]},
    ))
    return len(rows)


def apply_forecasts_to_sources(db: Session, issue_month: Optional[date] = None) -> int:
    """Reporte la prévision à 1 mois sur les sources de l'application (statut et score affichés par la carte).

    `risk_score` = probabilité d'atteindre le niveau critique à 1 mois. Les sources dont le
    réservoir n'est pas modélisé passent en « inconnu ».
    """
    fc = forecasts_frame(db, issue_month)
    if fc.empty:
        return 0
    h1 = fc[fc["horizon"] == fc["horizon"].min()].set_index("reservoir_id")
    links = db.execute(select(ReservoirSource.source_id, ReservoirSource.reservoir_id)).all()
    updated = 0
    for source_id, reservoir_id in links:
        source = db.get(WaterSource, source_id)
        if reservoir_id not in h1.index:
            # Réservoir non modélisé (aucune eau détectée par satellite) : pas de statut v2 trompeur
            source.status = "inconnu"
            updated += 1
            continue
        source.status = h1.loc[reservoir_id, "status"]
        source.risk_score = round(float(h1.loc[reservoir_id, "p_critical"]), 3)
        source.date_analyse = date.today()
        updated += 1
    return updated


# --------------------------------------------------------------------------- #
# Bulletin mensuel
# --------------------------------------------------------------------------- #
def build_bulletin(db: Session, issue_month: Optional[date] = None, include_rejected: bool = False) -> dict:
    """État de toutes les retenues : mesure du mois, évolution, prévisions, classement par risque."""
    fc = forecasts_frame(db, issue_month)
    if fc.empty:
        raise LookupError("Aucune prévision en base")
    issue = fc["issue_month"].iloc[0]
    prev = (pd.Timestamp(issue) - pd.DateOffset(months=1)).date()

    obs = pd.DataFrame(db.execute(
        select(WaterAreaObservation.reservoir_id, WaterAreaObservation.month, WaterAreaObservation.fill,
               WaterAreaObservation.area_ha, WaterAreaObservation.volume_m3, WaterAreaObservation.area_source)
        .where(WaterAreaObservation.month.in_([issue, prev]))
    ).all(), columns=["reservoir_id", "month", "fill", "area_ha", "volume_m3", "area_source"])
    now = obs[obs["month"] == issue].set_index("reservoir_id")
    before = obs[obs["month"] == prev].set_index("reservoir_id")["fill"]

    res = pd.DataFrame(db.execute(
        select(Reservoir.id, Reservoir.origin, Reservoir.a_ref_ha, Reservoir.validation,
               func.ST_Y(func.ST_Centroid(Reservoir.geometry)), func.ST_X(func.ST_Centroid(Reservoir.geometry)))
    ).all(), columns=["reservoir_id", "origin", "a_ref_ha", "validation", "lat", "lon"]).set_index("reservoir_id")
    if not include_rejected:
        res = res[res["validation"] != "rejete"]
    sources = pd.DataFrame(db.execute(select(ReservoirSource.reservoir_id, ReservoirSource.source_id)).all(),
                           columns=["reservoir_id", "source_id"]).groupby("reservoir_id")["source_id"].apply(list)

    wide = fc.pivot(index="reservoir_id", columns="horizon", values=["fill_pred", "fill_lo80", "fill_hi80", "p_critical"])
    rows = []
    for rid, r in res.iterrows():
        if rid not in wide.index:
            continue
        fill_now = _none(now["fill"].get(rid)) if rid in now.index else None
        fill_prev = _none(before.get(rid))
        horizons = sorted(fc["horizon"].unique())
        rows.append({
            "reservoir_id": rid,
            "origin": r["origin"],
            "validation": r["validation"],
            "source_ids": sources.get(rid, []),
            "lat": round(float(r["lat"]), 5),
            "lon": round(float(r["lon"]), 5),
            "a_ref_ha": round(float(r["a_ref_ha"]), 2),
            "fill_now": None if fill_now is None else round(float(fill_now), 4),
            "fill_change_1m": None if fill_now is None or fill_prev is None else round(float(fill_now - fill_prev), 4),
            "area_ha": _round(now["area_ha"].get(rid) if rid in now.index else None, 2),
            "volume_m3": _round(now["volume_m3"].get(rid) if rid in now.index else None, 0),
            "area_source": now["area_source"].get(rid) if rid in now.index else None,
            "status": fc[(fc.reservoir_id == rid) & (fc.horizon == horizons[0])]["status"].iloc[0],
            "p_critical_max": round(float(wide.loc[rid, "p_critical"].max()), 4),
            "forecast": [
                {"horizon": int(h), "fill_pred": round(float(wide.loc[rid, ("fill_pred", h)]), 4),
                 "fill_lo80": round(float(wide.loc[rid, ("fill_lo80", h)]), 4),
                 "fill_hi80": round(float(wide.loc[rid, ("fill_hi80", h)]), 4),
                 "p_critical": round(float(wide.loc[rid, ("p_critical", h)]), 4)}
                for h in horizons
            ],
        })
    rows.sort(key=lambda x: (-x["p_critical_max"], x["fill_now"] if x["fill_now"] is not None else 9))
    statuses = pd.Series([r["status"] for r in rows]).value_counts().to_dict()
    return {
        "issue_month": pd.Timestamp(issue).strftime("%Y-%m"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "critical_fill": settings.critical_fill,
        "model_version": fc["model_version"].iloc[0],
        "n_reservoirs": len(rows),
        "status_counts": {k: int(v) for k, v in statuses.items()},
        "reservoirs": rows,
    }


def bulletin_to_csv(bulletin: dict) -> str:
    flat = []
    for r in bulletin["reservoirs"]:
        row = {k: v for k, v in r.items() if k not in ("forecast", "source_ids")}
        row["source_ids"] = " ".join(map(str, r["source_ids"]))
        for f in r["forecast"]:
            for k in ("fill_pred", "fill_lo80", "fill_hi80", "p_critical"):
                row[f"{k}_h{f['horizon']}"] = f[k]
        flat.append(row)
    return pd.DataFrame(flat).to_csv(index=False)


def _round(value, ndigits):
    value = _none(value)
    return None if value is None else round(float(value), ndigits)


def region_geojson(db: Session) -> dict[str, dict]:
    rows = db.execute(text("SELECT id, ST_AsGeoJSON(region) FROM reservoirs WHERE modelable")).all()
    return {rid: json.loads(g) for rid, g in rows}
