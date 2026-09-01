from __future__ import annotations

import logging
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..config import settings
from .ingest import collect_latest_period

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler:
    """Démarre le scheduler APScheduler si activé dans la config."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    scheduler = BackgroundScheduler()

    # Collecte hebdomadaire des dernières mesures NDWI.
    scheduler.add_job(
        collect_latest_period,
        IntervalTrigger(hours=settings.collect_hours),
        id="collect_weekly",
        replace_existing=True,
        max_instances=1,
    )

    _scheduler = scheduler
    scheduler.start()
    logger.info("Scheduler démarré (collecte toutes les %d h)", settings.collect_hours)
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
