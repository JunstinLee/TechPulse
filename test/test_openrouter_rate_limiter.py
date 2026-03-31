import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from utils.openrouter_rate_limiter import OpenRouterRateLimiter


class OpenRouterRateLimiterTests(unittest.IsolatedAsyncioTestCase):
    async def test_acquire_succeeds_when_window_and_interval_zero(self):
        lim = OpenRouterRateLimiter()
        with patch("utils.openrouter_rate_limiter.Config.OPENROUTER_REQUESTS_PER_MINUTE", 0), patch(
            "utils.openrouter_rate_limiter.Config.MIN_REQUEST_INTERVAL", 0.0
        ), patch("utils.openrouter_rate_limiter.time.time", return_value=1_000_000.0):
            await lim.acquire()

    async def test_acquire_waits_until_min_interval_elapsed(self):
        lim = OpenRouterRateLimiter()
        clock = iter([100.0, 100.0, 106.0])

        def fake_time():
            return next(clock)

        sleeps = []

        async def fake_sleep(dt):
            sleeps.append(dt)

        with patch("utils.openrouter_rate_limiter.Config.OPENROUTER_REQUESTS_PER_MINUTE", 0), patch(
            "utils.openrouter_rate_limiter.Config.MIN_REQUEST_INTERVAL", 5.0
        ), patch("utils.openrouter_rate_limiter.time.time", side_effect=fake_time), patch(
            "utils.openrouter_rate_limiter.asyncio.sleep", side_effect=fake_sleep
        ):
            await lim.acquire()
            await lim.acquire()

        self.assertTrue(sleeps)
        self.assertGreaterEqual(sleeps[0], 5.0)

    def test_enter_cooldown_extends_deadline(self):
        lim = OpenRouterRateLimiter()
        with patch("utils.openrouter_rate_limiter.Config.OPENROUTER_429_COOLDOWN_SECONDS", 30.0), patch(
            "utils.openrouter_rate_limiter.time.time", return_value=1000.0
        ):
            lim.enter_cooldown(5.0)
        self.assertGreaterEqual(lim._cooldown_until, 1000.0 + 30.0)


if __name__ == "__main__":
    unittest.main()
