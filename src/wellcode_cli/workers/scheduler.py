"""Background metric collection scheduler using APScheduler."""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..services.collector import collect_all

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _run_collection(days_back: int = 7):
    """Execute a metric collection run."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days_back)
    logger.info("Scheduled collection: %s to %s", start.date(), now.date())
    try:
        summary = collect_all(start, now)
        logger.info("Collection complete: %s", summary)
    except Exception as e:
        logger.error("Scheduled collection failed: %s", e)


def start_scheduler(
    interval_hours: int = 6,
    days_back: int = 7,
) -> BackgroundScheduler:
    """Start the background scheduler for periodic metric collection."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler()

    _scheduler.add_job(
        _run_collection,
        trigger=IntervalTrigger(hours=interval_hours),
        kwargs={"days_back": days_back},
        id="metric_collection",
        name="Periodic metric collection",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Scheduler started: collecting every %d hours", interval_hours)
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=True)
        _scheduler = None
        logger.info("Scheduler stopped")
