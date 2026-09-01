"""
Entraînement du modèle v2 : prédit le nombre de périodes avant tarissement
(NDWI < 0.2) à partir des observations NDWI réelles stockées en base.

Usage :
  python -m ml.train
"""
from __future__ import annotations

import json
import logging
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("train")

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score, mean_squared_error
from sklearn.preprocessing import StandardScaler, LabelEncoder
import joblib

from app.database import SessionLocal
from app.models import NdwiObservation, WaterSource
from app.config import settings

DRY_NDWI = 0.2
RUNS_DIR = Path(__file__).resolve().parent / "runs"
ARTIFACT_NAMES = ["model.pkl", "scaler.pkl", "encoder_saison.pkl", "encoder_ville.pkl"]

FEATURES = [
    "ndwi", "ndwi_t1", "ndwi_t2", "ndwi_t3",
    "pente_court", "pente_moyen", "ndwi_moy_src", "ndvi",
    "saison_encoded", "ville_encoded", "latitude", "longitude",
]


def load_observations() -> pd.DataFrame:
    db = SessionLocal()
    try:
        rows = db.query(NdwiObservation, WaterSource).join(WaterSource).all()
        records = []
        for obs, src in rows:
            if obs.periode is None or obs.ndwi is None:
                continue
            records.append({
                "source_id": obs.source_id,
                "longitude": src.longitude,
                "latitude": src.latitude,
                "periode": obs.periode,
                "saison": obs.saison or "seche",
                "ndwi": obs.ndwi,
                "ndvi": obs.ndvi or 0.0,
                "ville": src.zone or "Ouagadougou",
            })
    finally:
        db.close()

    df = pd.DataFrame(records)
    if df.empty:
        raise RuntimeError("Aucune observation en base. Lance d'abord scripts/backfill_ndwi.py")
    return df


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, LabelEncoder, LabelEncoder]:
    """Retourne (df_features, encoder_saison, encoder_ville) cohérents."""
    df = df.sort_values(["source_id", "periode"]).copy()

    le_saison = LabelEncoder()
    le_ville = LabelEncoder()
    df["saison_encoded"] = le_saison.fit_transform(df["saison"])
    df["ville_encoded"] = le_ville.fit_transform(df["ville"])

    # Lags + tendances par source
    df["ndwi_t1"] = df.groupby("source_id")["ndwi"].shift(1)
    df["ndwi_t2"] = df.groupby("source_id")["ndwi"].shift(2)
    df["ndwi_t3"] = df.groupby("source_id")["ndwi"].shift(3)
    df["pente_court"] = df["ndwi"] - df["ndwi_t1"]
    df["pente_moyen"] = df["ndwi"] - df["ndwi_t3"]
    df["ndwi_moy_src"] = df.groupby("source_id")["ndwi"].transform("mean")

    # Cible : périodes avant tarissement.
    def periods_until_dry(values: np.ndarray) -> np.ndarray:
        out = np.full(len(values), np.nan)
        for i in range(len(values)):
            future = values[i + 1:]
            if len(future) == 0:
                continue
            idx = np.where(future < DRY_NDWI)[0]
            out[i] = (idx[0] + 1) if len(idx) > 0 else 20
        return out

    df["periods_until_dry"] = df.groupby("source_id", group_keys=False)["ndwi"].transform(
        periods_until_dry
    )

    df = df.dropna(subset=["ndwi_t1", "ndwi_t2", "periods_until_dry"])
    return df, le_saison, le_ville


def run() -> None:
    df = load_observations()
    logger.info("Observations chargées : %d lignes", len(df))

    df, le_saison, le_ville = build_features(df)
    logger.info("Après feature engineering : %d lignes", len(df))
    if len(df) < 20:
        raise RuntimeError(
            f"Trop peu de données exploitables ({len(df)}). "
            "Collecte plus d'historique avant d'entraîner."
        )

    X = df[FEATURES].fillna(0.0)
    y = df["periods_until_dry"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    models = {
        "RandomForest": RandomForestRegressor(
            n_estimators=150, max_depth=15, min_samples_split=5, random_state=42
        ),
        "GradientBoosting": GradientBoostingRegressor(
            n_estimators=150, learning_rate=0.1, max_depth=5, random_state=42
        ),
    }

    best, best_name, best_mae, results = None, "", float("inf"), {}
    for name, model in models.items():
        if name == "GradientBoosting":
            model.fit(X_train_scaled, y_train)
            y_pred = model.predict(X_test_scaled)
        else:
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)
        results[name] = {"mae": round(float(mae), 3), "rmse": round(float(rmse), 3), "r2": round(float(r2), 3)}
        logger.info("%s → MAE %.3f | RMSE %.3f | R² %.3f", name, mae, rmse, r2)
        if mae < best_mae:
            best, best_name, best_mae = model, name, mae

    # ---- Sauvegarde dans ml/runs/run_<ts> ----
    run_dir = RUNS_DIR / f"run_{int(time.time())}"
    run_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(best, run_dir / "model.pkl")
    joblib.dump(scaler, run_dir / "scaler.pkl")
    joblib.dump(le_saison, run_dir / "encoder_saison.pkl")
    joblib.dump(le_ville, run_dir / "encoder_ville.pkl")
    with open(run_dir / "features.json", "w", encoding="utf-8") as f:
        json.dump(FEATURES, f)
    metadata = {"model": best_name, **results[best_name], "n_rows": int(len(df))}
    with open(run_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f)

    # ---- Pointe ml/runs/latest vers ce run (copie) ----
    latest = RUNS_DIR / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    for name in ARTIFACT_NAMES + ["features.json", "metadata.json"]:
        shutil.copy(run_dir / name, latest / name)

    # ---- Rapport ----
    report = {
        **metadata,
        "run_dir": str(run_dir),
        "feature_importance": _importance(best, FEATURES),
    }
    with open(run_dir / "report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info("Meilleur modèle : %s (MAE %.3f) → %s", best_name, best_mae, run_dir)
    logger.info("Artifacts copiés vers ml/runs/latest")


def _importance(model, features) -> dict[str, float]:
    if not hasattr(model, "feature_importances_"):
        return {}
    imp = model.feature_importances_
    ranked = sorted(zip(features, imp), key=lambda x: x[1], reverse=True)
    return {f: round(float(v), 4) for f, v in ranked[:10]}


if __name__ == "__main__":
    run()
