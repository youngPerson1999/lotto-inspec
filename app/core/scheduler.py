"""Background scheduler that keeps Lotto draws up to date."""

from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.services.analysis_tasks import (
    refresh_dependency_analysis,
    refresh_lotto_summary,
    refresh_pattern_analysis,
    refresh_randomness_suite,
    refresh_runs_sum_analysis,
)
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


def _refresh_weekly_analysis() -> None:
    """Recompute cached analysis snapshots."""

    settings = get_settings()
    try:
        refresh_lotto_summary()
        refresh_dependency_analysis()
        refresh_runs_sum_analysis()
        refresh_pattern_analysis()
        refresh_randomness_suite(
            encoding=settings.analysis_randomness_encoding,
            block_size=settings.analysis_randomness_block_size,
            serial_block=settings.analysis_randomness_serial_block,
        )
        logger.info("Weekly analysis refresh completed")
    except Exception:  # noqa: BLE001
        logger.exception("Weekly analysis refresh failed")


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
    if settings.use_database_storage:
        analysis_tz = settings.analysis_scheduler_timezone or settings.scheduler_timezone
        try:
            analysis_timezone = ZoneInfo(analysis_tz)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Invalid analysis timezone %s, falling back to %s",
                analysis_tz,
                timezone,
            )
            analysis_timezone = timezone

        analysis_trigger = CronTrigger(
            day_of_week=settings.analysis_scheduler_day_of_week,
            hour=settings.analysis_scheduler_hour,
            minute=settings.analysis_scheduler_minute,
            timezone=analysis_timezone,
        )
        scheduler.add_job(
            _refresh_weekly_analysis,
            trigger=analysis_trigger,
            id="weekly_lotto_analysis",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info(
            "Weekly analysis refresh scheduled: %s at %02d:%02d (%s)",
            settings.analysis_scheduler_day_of_week,
            settings.analysis_scheduler_hour,
            settings.analysis_scheduler_minute,
            analysis_timezone,
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
