"""Background job of the data retention policy: anonymize old records while the server is awake.

Free hosting puts the instance to sleep after a while; the job runs again on the next wake-up (the application
start), so records are erased the next time the service is used. Each run is a few stored procedure calls.
"""

import asyncio
import logging
from typing import Callable

from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)


async def run_retention_loop(purge: Callable[[], int], interval_hours: float) -> None:
    """Call `purge` now and then every `interval_hours`. Failures are logged and never stop the loop."""
    interval = max(60.0, interval_hours * 3600)
    while True:
        try:
            await run_in_threadpool(purge)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # the database may be asleep or restarting: try again at the next tick
            logger.warning("Retention job failed: %s", exc)
        await asyncio.sleep(interval)
