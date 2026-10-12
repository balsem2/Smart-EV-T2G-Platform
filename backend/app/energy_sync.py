"""Background refresh of recent Austrian quarter-hour energy observations."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.config import settings
from scripts.sync_energy_charts import sync_once


logger = logging.getLogger(__name__)

sync_status: dict[str, str | None] = {
    "state": "disabled" if not settings.energy_sync_enabled else "waiting",
    "last_success_at": None,
    "last_error": None,
}


async def run_energy_sync(stop_event: asyncio.Event) -> None:
    """Refresh once at startup and then at the configured interval."""
    while not stop_event.is_set():
        sync_status["state"] = "running"
        try:
            await asyncio.to_thread(sync_once, settings.energy_sync_days, False)
            sync_status.update(
                state="healthy",
                last_success_at=datetime.now(timezone.utc).isoformat(),
                last_error=None,
            )
        except Exception as error:  # keep the API available during source outages
            logger.warning("Automatic Austrian energy sync failed: %s", error)
            sync_status.update(state="degraded", last_error=str(error))

        try:
            await asyncio.wait_for(
                stop_event.wait(), timeout=settings.energy_sync_interval_seconds
            )
        except TimeoutError:
            continue

