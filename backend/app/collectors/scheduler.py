from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..config import settings
from .monthly import run_monthly_update

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _monthly_job() -> None:
    try:
        run_monthly_update()
    except Exception:  # noqa: BLE001  (déjà journalisé ; le scheduler doit survivre)
        logger.error("Mise à jour mensuelle v3 en échec, nouvel essai au prochain passage")


def start_scheduler() -> BackgroundScheduler:
    """Démarre le scheduler APScheduler si activé dans la config."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _monthly_job,
        IntervalTrigger(hours=settings.collect_hours),
        id="monthly_update_v3",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler = scheduler
    scheduler.start()
    logger.info("Scheduler démarré (mise à jour v3 vérifiée toutes les %d h)", settings.collect_hours)
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
