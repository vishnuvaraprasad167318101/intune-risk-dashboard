"""
sync.py — Scheduled background sync using APScheduler.

Runs a delta sync every N hours (configurable via SYNC_INTERVAL_HOURS).
Can be run standalone or imported and started from the FastAPI app.

Run standalone:
    python -m scheduler.sync
"""

import asyncio
import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("scheduler")

SYNC_INTERVAL_HOURS = int(os.getenv("SYNC_INTERVAL_HOURS", 6))


async def sync_job():
    """Scheduled sync job — runs a delta sync and logs results."""
    import backend.device_service as svc

    logger.info("Scheduled delta sync starting…")
    try:
        changed = await svc.delta_sync()
        state = svc.get_sync_state()
        logger.info(
            "Scheduled sync complete: %d changed, %d total devices cached.",
            changed, state.total_devices_cached,
        )
    except Exception as exc:
        logger.error("Scheduled sync failed: %s", exc)


async def main():
    """Run the scheduler as a standalone process."""
    import backend.device_service as svc

    # Initial full sync on startup
    logger.info("Running initial sync on scheduler startup…")
    await svc.initial_sync()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        sync_job,
        trigger=IntervalTrigger(hours=SYNC_INTERVAL_HOURS),
        id="delta_sync",
        name="Intune Delta Sync",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — delta sync every %d hour(s).", SYNC_INTERVAL_HOURS)

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    asyncio.run(main())
