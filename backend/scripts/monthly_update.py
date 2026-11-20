"""
Mise à jour mensuelle v3 en ligne de commande, pour un planificateur externe
(workflow GitHub Actions `.github/workflows/monthly-update.yml`, cron, tâche planifiée).

Sans mois indiqué, rattrape tous les mois manquants depuis le dernier mois en base
(au plus `--max-months` par passage), puis émet les prévisions de chacun.

Variables d'environnement : DATABASE_URL, GEE_SERVICE_ACCOUNT_KEY (et GEE_PROJECT si
différent du projet par défaut) ; MODEL_BUNDLE_URL et MODEL_BUNDLE_SHA256 pour
télécharger le paquet du modèle s'il est absent (`ml/runs/forecast_latest/bundle.joblib`).

Code de sortie : 0 succès ; 1 échec ; 2 données encore en retard après la mise à jour
(plus de STALE_AFTER_MONTHS mois). Un mois mal mesuré est signalé sans faire échouer.

Usage :
  python -m scripts.monthly_update
  python -m scripts.monthly_update --month 2026-10 --force
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("monthly_update")

from app.collectors.monthly import MAX_CATCH_UP, STALE_AFTER_MONTHS, run_monthly_update

OK, FAILED, STALE = 0, 1, 2


def markdown_summary(summary: dict) -> str:
    """Résumé lisible pour la page du run GitHub Actions."""
    lines = ["## Mise à jour mensuelle", ""]
    if summary["months"]:
        lines += ["| Mois | Retenues | Provenance |", "|---|---|---|"]
        for m in summary["months"]:
            sources = ", ".join(f"{k} {v}" for k, v in sorted(m["sources"].items()))
            lines.append(f"| {m['month']} | {m['reservoirs']} | {sources} |")
    else:
        lines.append("Aucun nouveau mois publié par ERA5-Land et CHIRPS : rien à collecter.")
    lines += ["", f"- Dernier mois en base : **{summary['latest_month']}** "
                  f"({summary['months_behind']} mois de retard sur le dernier mois complet)",
              f"- Prévisions émises pour {summary['issue_month']} : {summary['forecasts']} ; "
              f"statuts à 1 mois : {summary['status_counts']}",
              f"- Mois d'assèchement : {summary.get('drying_forecasts', 0)} retenues"
              + (f" ({summary['drying_note']})" if summary.get("drying_note") else "")]
    if summary.get("verification"):
        lines += ["", "### Vérification des prévisions qui visaient ces mois", "",
                  "| Horizon | Prévisions | Erreur | Normale | Gain sur la normale | Dans l'intervalle 80 % | Alertes justes / fausses |",
                  "|---|---|---|---|---|---|---|"]
        for r in summary["verification"]:
            gain = "—" if r["skill_vs_normal"] is None else f"{r['skill_vs_normal']:+.0%}"
            normal = "—" if r["normal_mae"] is None else f"{r['normal_mae']:.3f}"
            lines.append(f"| {r['horizon']} mois | {r['n']} | {r['mae']:.3f} | {normal} | {gain} | "
                         f"{r['coverage_80']:.0%} | {r['hits']} / {r['false_alarms']} |")
        lines.append("")
    if summary["deferred_months"]:
        lines.append(f"- {summary['deferred_months']} mois reportés au passage suivant")
    lines += [f"- ⚠️ {w}" for w in summary["warnings"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--month", help="mois à collecter (AAAA-MM) ; défaut : tous les mois manquants")
    parser.add_argument("--force", action="store_true", help="recollecter un mois déjà en base")
    parser.add_argument("--max-months", type=int, default=MAX_CATCH_UP, help="mois collectés au plus par passage")
    args = parser.parse_args(argv)

    try:
        summary = run_monthly_update(month=args.month, force=args.force, max_months=args.max_months)
    except Exception:  # noqa: BLE001  (le détail est déjà journalisé)
        logger.error("Mise à jour mensuelle en échec")
        return FAILED

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as out:
            out.write(markdown_summary(summary))
    if os.environ.get("GITHUB_ACTIONS"):
        for w in summary["warnings"]:
            print(f"::warning::{w}")   # annotation visible sur la page du run
    if summary["data"] == "stale":
        logger.error("Données en retard : dernier mois %s, %s mois de retard (seuil : %d)",
                     summary["latest_month"], summary["months_behind"], STALE_AFTER_MONTHS)
        return STALE
    return OK


if __name__ == "__main__":
    sys.exit(main())
