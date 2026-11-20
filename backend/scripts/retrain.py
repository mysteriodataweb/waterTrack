"""
Réentraînement annuel du modèle v3 avec contrôle avant mise en service (`ml/retrain.py`).

À lancer une fois par an, quand les mois de la saison des pluies sont collectés
(fin novembre), par le workflow `.github/workflows/retrain.yml` ou à la main :

  python -m scripts.retrain                                          # panel et bilan réel lus dans la base
  python -m scripts.retrain --panel data/gee/panel_monthly.parquet   # hors ligne, sans bilan réel
  python -m scripts.retrain --bundle chemin/bundle.joblib            # autre champion que forecast_latest

Écrit `ml/runs/forecast_<horodatage>/` : bundle.joblib (candidat), model_card.json, report.md.
`--promote` copie le candidat dans `ml/runs/forecast_latest/` si le contrôle est passé.
La mise en service en production reste manuelle : publier le paquet dans une release
GitHub et mettre à jour MODEL_BUNDLE_URL et MODEL_BUNDLE_SHA256 (voir backend/README.md).

Code de sortie : 0 candidat prêt à mettre en service ; 2 champion conservé ; 1 échec.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("retrain")

import joblib
import pandas as pd

from ml.forecasting import LATEST_BUNDLE, RUNS_DIR, load_bundle
from ml.retrain import Retraining, retrain

PROMOTE, FAILED, KEEP = 0, 1, 2


def model_version(bundle: dict) -> str:
    """Même libellé que les prévisions enregistrées en base (`app/collectors/monthly.py`)."""
    return f"{bundle.get('version')} ({bundle.get('created')})"


def load_inputs(panel_path: Path | None, champion: dict) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Panel mensuel et bilan réel du champion (prévisions émises puis vérifiées), lus dans la base par défaut."""
    if panel_path is not None:
        return pd.read_parquet(panel_path), None
    from app.database import SessionLocal
    from app.services import reservoirs as svc

    with SessionLocal() as db:
        panel = svc.load_panel(db)
        record = svc.verification_frame(db)
    if len(record):
        record = record[record["model_version"] == model_version(champion)]
    return panel, record


def report_markdown(result: Retraining, champion: dict, sha256: str) -> str:
    verdict = ("**Candidat prêt à mettre en service** : tous les contrôles sont passés."
               if result.decision == "promote" else "**Champion conservé** : au moins un contrôle n'est pas passé.")
    lines = ["## Réentraînement annuel du modèle v3", "", verdict, "",
             f"- Champion : {model_version(champion)}",
             f"- Fenêtre d'évaluation (mois cibles) : {result.window[0]} à {result.window[1]}",
             f"- Empreinte SHA-256 du candidat : `{sha256}`", "",
             "| Horizon | Prévisions | Erreur challenger | Erreur normale | Gain sur la normale | Dans l'intervalle 80 % | Alertes justes / fausses |",
             "|---|---|---|---|---|---|---|"]
    for h, s in sorted(result.challenger.items()):
        gain = "—" if s["skill_vs_normal"] is None else f"{s['skill_vs_normal']:+.1%}"
        normal = result.normal[h]["mae"]
        lines.append(f"| {h} mois | {s['n']} | {s['mae']:.3f} | {'—' if normal is None else f'{normal:.3f}'} | "
                     f"{gain} | {s['coverage_80']:.0%} | {s['hits']} / {s['false_alarms']} |")
    if result.champion:
        lines += ["", "Bilan réel du champion sur la fenêtre (prévisions émises puis vérifiées) :", "",
                  "| Horizon | Prévisions | Erreur du champion |", "|---|---|---|"]
        lines += [f"| {h} mois | {s['n']} | {s['mae']:.3f} |" for h, s in sorted(result.champion.items())]
    else:
        lines += ["", "Pas encore de bilan réel du champion sur la fenêtre : la comparaison porte sur la normale saisonnière."]
    lines += ["", "| Contrôle | Valeur | Seuil | Résultat |", "|---|---|---|---|"]
    for c in result.checks:
        value = "—" if c["value"] is None else f"{c['value']:+.1%}" if "gain" in c["check"] or "erreur" in c["check"] else f"{c['value']:.0%}"
        lines.append(f"| {c['check']} | {value} | {c['threshold']} | {'passé' if c['passed'] else '**échoué**'} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--panel", type=Path, help="panel Parquet (défaut : la base de données)")
    parser.add_argument("--bundle", type=Path, default=LATEST_BUNDLE, help="paquet du champion")
    parser.add_argument("--window-months", type=int, default=12, help="mois cibles de la fenêtre d'évaluation")
    parser.add_argument("--out", type=Path, help="dossier de sortie (défaut : ml/runs/forecast_<horodatage>)")
    parser.add_argument("--promote", action="store_true", help="copier le candidat dans forecast_latest s'il passe le contrôle")
    args = parser.parse_args(argv)

    try:
        champion = load_bundle(args.bundle)
        panel, record = load_inputs(args.panel, champion)
        logger.info("Panel : %d lignes, %d réservoirs ; bilan réel du champion : %d prévisions vérifiées",
                    len(panel), panel["reservoir_id"].nunique(), 0 if record is None else len(record))
        result = retrain(panel, champion, record, window_months=args.window_months)
    except Exception:  # noqa: BLE001
        logger.exception("Réentraînement en échec")
        return FAILED

    out = args.out or RUNS_DIR / f"forecast_{datetime.now():%Y%m%d_%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(result.bundle, out / "bundle.joblib", compress=3)
    sha256 = hashlib.sha256((out / "bundle.joblib").read_bytes()).hexdigest()
    card = {"version": result.bundle.get("version"), "created": result.bundle["created"],
            "data_end": result.bundle["data_end"], "retrained_from": result.bundle["retrained_from"],
            "sha256": sha256, **result.bundle["retraining"]}
    (out / "model_card.json").write_text(json.dumps(card, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    report = report_markdown(result, champion, sha256)
    (out / "report.md").write_text(report, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(report)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"decision={result.decision}\nsha256={sha256}\nrun_dir={out}\n")
    print(report)
    logger.info("Candidat écrit dans %s", out)

    if result.decision != "promote":
        return KEEP
    if args.promote:
        LATEST_BUNDLE.parent.mkdir(parents=True, exist_ok=True)
        for name in ("bundle.joblib", "model_card.json", "report.md"):
            shutil.copy2(out / name, LATEST_BUNDLE.parent / name)
        logger.info("Candidat copié dans %s", LATEST_BUNDLE.parent)
    return PROMOTE


if __name__ == "__main__":
    sys.exit(main())
