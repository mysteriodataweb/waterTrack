"""
Inférence du modèle v3 : prévision du taux de remplissage à 1-3 mois.

Partagé par le notebook (§13), le chargement en base (`scripts/load_v3.py`)
et la mise à jour mensuelle de l'API (`app/collectors/monthly.py`) : une seule
implémentation, donc une seule façon de calculer une prévision.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from . import features as F

RUNS_DIR = Path(__file__).resolve().parent / "runs"
LATEST_BUNDLE = RUNS_DIR / "forecast_latest" / "bundle.joblib"

# Correspondance prévision -> statut affiché par l'application
DRY_FILL = 0.05          # remplissage prévu sous lequel la retenue est considérée « tarie »
ALERT_PROBABILITY = 0.5  # probabilité calibrée de niveau critique déclenchant « à risque »


def load_bundle(path: Path = LATEST_BUNDLE) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Paquet de modèles introuvable : {path} (exécuter le notebook)")
    return joblib.load(path)


def status_from(fill_pred: pd.Series, p_critical: pd.Series) -> np.ndarray:
    return np.select([fill_pred < DRY_FILL, p_critical >= ALERT_PROBABILITY], ["tari", "à risque"], "actif")


def forecast(bundle: dict, panel_hist: pd.DataFrame, issue: pd.Timestamp | None = None) -> pd.DataFrame:
    """Prévisions émises à la fin du mois `issue` (par défaut le dernier mois du panel).

    `panel_hist` : panel mensuel (reservoir_id, date, fill, area_source + forçages climatiques).
    Les réservoirs sans valeur de remplissage au mois d'émission sont ignorés.
    """
    issue = panel_hist["date"].max() if issue is None else pd.Timestamp(issue)
    known = set(bundle["static"].index)
    panel_hist = panel_hist[panel_hist["reservoir_id"].isin(known)]
    out = []
    for h in bundle["horizons"]:
        m = bundle["models"][h]
        rows = F.build_rows(panel_hist, h, bundle["climatology"], bundle["static"], with_target=False)
        rows = rows[(rows["date"] == issue) & rows["fill_l0"].notna()]
        if rows.empty:
            continue
        X = rows[bundle["features"]]
        base = rows["fill_l0"].values
        med = m["median"].predict(X) + (base if m["target_mode"] == "delta" else 0)
        lo = m["q_lo"].predict(X) + base - m["conformal_q"]
        hi = m["q_hi"].predict(X) + base + m["conformal_q"]
        p_raw = m["classifier"].predict_proba(X)[:, 1]
        out.append(pd.DataFrame({
            "reservoir_id": rows["reservoir_id"].values,
            "issue_month": issue.strftime("%Y-%m"),
            "horizon": h,
            "target_month": rows["target_date"].dt.strftime("%Y-%m").values,
            "fill_now": base,
            "fill_pred": np.clip(med, 0, 1.5),
            "fill_lo80": np.clip(lo, 0, 1.5),
            "fill_hi80": np.clip(hi, 0, 1.5),
            # Calibration isotonique seulement si elle améliorait le score de Brier en validation
            "p_critical": p_raw if m["calibrator"] is None else m["calibrator"].predict(p_raw),
        }))
    if not out:
        return pd.DataFrame(columns=["reservoir_id", "issue_month", "horizon", "target_month", "fill_now",
                                     "fill_pred", "fill_lo80", "fill_hi80", "p_critical", "status"])
    fc = pd.concat(out, ignore_index=True)
    fc["status"] = status_from(fc["fill_pred"], fc["p_critical"])
    return fc
