"""Automatic recent-energy refresh tests."""

import asyncio
import unittest
from unittest.mock import patch

from app.energy_sync import run_energy_sync, sync_status


class EnergySyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_runs_immediately_and_repeats_on_interval(self):
        stop_event = asyncio.Event()
        with (
            patch("app.energy_sync.sync_once") as sync_once,
            patch("app.energy_sync.settings.energy_sync_interval_seconds", 0.01),
        ):
            task = asyncio.create_task(run_energy_sync(stop_event))
            await asyncio.sleep(0.035)
            stop_event.set()
            await task

        self.assertGreaterEqual(sync_once.call_count, 2)
        self.assertEqual(sync_status["state"], "healthy")
        self.assertIsNotNone(sync_status["last_success_at"])


if __name__ == "__main__":
    unittest.main()
