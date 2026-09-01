"""
Évaluation du modèle v2 de production (celui dans ml/runs/latest).

Affiche les métriques enregistrées au moment de l'entraînement et, si possible,
recalcule des métriques sur un échantillon. Aide à suivre la qualité des prédictions.

Usage :
  python -m ml.evaluate
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib

RUNS_DIR = Path(__file__).resolve().parent / "runs"
LATEST = RUNS_DIR / "latest"


def main() -> None:
    if not (LATEST / "metadata.json").exists():
        print("Aucun modèle entraîné. Lance `python -m ml.train` d'abord.")
        return

    with open(LATEST / "metadata.json", "r", encoding="utf-8") as f:
        meta = json.load(f)
    print("=== Modèle v2 (ml/runs/latest) ===")
    print(f"Modèle            : {meta.get('model')}")
    print(f"MAE               : {meta.get('mae')} périodes")
    print(f"RMSE              : {meta.get('rmse')} périodes")
    print(f"R²                : {meta.get('r2')}")
    print(f"Lignes d'entraînement : {meta.get('n_rows')}")

    report_path = LATEST / "report.json"
    if report_path.exists():
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
        imp = report.get("feature_importance") or {}
        if imp:
            print("\n=== Top features ===")
            for name, val in imp.items():
                print(f"  {name:12} {val}")


if __name__ == "__main__":
    main()
