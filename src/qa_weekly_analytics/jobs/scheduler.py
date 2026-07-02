from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_PATH = _REPO_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from qa_weekly_analytics.jobs.publish_week import run_publish_week  # noqa: E402
from qa_weekly_analytics.storage.settings import Settings, SettingsError  # noqa: E402

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _scheduled_job() -> None:
    logger.info("Ejecutando job programado: publish_week")
    exit_code = run_publish_week(to_sheets=True, to_excel=True, force=False)
    if exit_code != 0:
        logger.error("Job programado falló con código %s", exit_code)


def start_scheduler(settings: Settings | None = None) -> BackgroundScheduler | None:
    """Inicia APScheduler si SCHEDULER_ENABLED=true en .env."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    try:
        settings = settings or Settings.from_env()
    except SettingsError as exc:
        logger.warning("Scheduler no iniciado: %s", exc)
        return None

    if not settings.SCHEDULER_ENABLED:
        return None

    _scheduler = BackgroundScheduler()
    trigger = CronTrigger(
        day_of_week=settings.SCHEDULER_CRON_DAY,
        hour=settings.SCHEDULER_CRON_HOUR,
        minute=settings.SCHEDULER_CRON_MINUTE,
    )
    _scheduler.add_job(_scheduled_job, trigger=trigger, id="publish_weekly_snapshot", replace_existing=True)
    _scheduler.start()
    logger.info(
        "Scheduler iniciado: %s %02d:%02d",
        settings.SCHEDULER_CRON_DAY,
        settings.SCHEDULER_CRON_HOUR,
        settings.SCHEDULER_CRON_MINUTE,
    )
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler detenido")
