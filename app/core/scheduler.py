"""Background scheduler that keeps Lotto draws up to date."""

from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.services.lotto import sync_draw_storage

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _sync_latest_draws() -> None:
    """Fetch the newest Lotto draw and persist it."""

    try:
        result = sync_draw_storage()
        logger.info(
            "Weekly Lotto sync complete (latest=%s inserted=%s)",
            result.latest,
            result.inserted,
        )
    except Exception:  # noqa: BLE001  # log but keep scheduler alive
        logger.exception("Weekly Lotto sync failed")


def start_scheduler() -> None:
    """Start the APScheduler instance if not already running."""

    global _scheduler  # noqa: PLW0603
    if _scheduler is not None and _scheduler.running:
        return

    settings = get_settings()
    try:
        timezone = ZoneInfo(settings.scheduler_timezone)
    except Exception:  # noqa: BLE001  # invalid tz falls back to UTC
        logger.warning(
            "Invalid timezone %s, falling back to UTC",
            settings.scheduler_timezone,
        )
        timezone = ZoneInfo("UTC")

    scheduler = AsyncIOScheduler(timezone=timezone)
    trigger = CronTrigger(
        day_of_week=settings.scheduler_day_of_week,
        hour=settings.scheduler_hour,
        minute=settings.scheduler_minute,
        timezone=timezone,
    )
    scheduler.add_job(
        _sync_latest_draws,
        trigger=trigger,
        id="weekly_lotto_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Weekly Lotto sync scheduled: %s at %02d:%02d (%s)",
        settings.scheduler_day_of_week,
        settings.scheduler_hour,
        settings.scheduler_minute,
        timezone,
    )


def stop_scheduler() -> None:
    """Shutdown the scheduler on application exit."""

    global _scheduler  # noqa: PLW0603
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None


__all__ = ["start_scheduler", "stop_scheduler"]
