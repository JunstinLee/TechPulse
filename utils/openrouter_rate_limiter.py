import asyncio
import logging
import threading
import time
from collections import deque
from typing import Deque

from utils.config import Config


logger = logging.getLogger("OpenRouterRateLimiter")


class OpenRouterRateLimiter:
    """Shared limiter for all OpenRouter requests in the current process."""

    def __init__(self):
        self._request_times: Deque[float] = deque()
        self._cooldown_until = 0.0
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        window_start = now - 60.0
        while self._request_times and self._request_times[0] <= window_start:
            self._request_times.popleft()

    def _reserve_slot(self) -> tuple[float, str, int]:
        now = time.time()
        with self._lock:
            self._prune(now)

            wait_for_cooldown = max(0.0, self._cooldown_until - now)

            wait_for_window = 0.0
            if (
                Config.OPENROUTER_REQUESTS_PER_MINUTE > 0
                and len(self._request_times) >= Config.OPENROUTER_REQUESTS_PER_MINUTE
            ):
                oldest = self._request_times[0]
                wait_for_window = max(0.0, 60.0 - (now - oldest))

            wait_for_interval = 0.0
            if self._request_times:
                elapsed = now - self._request_times[-1]
                wait_for_interval = max(0.0, Config.MIN_REQUEST_INTERVAL - elapsed)

            wait_time = max(wait_for_cooldown, wait_for_window, wait_for_interval)
            reason = "ready"
            if wait_time == wait_for_cooldown and wait_for_cooldown > 0:
                reason = "cooldown"
            elif wait_time == wait_for_window and wait_for_window > 0:
                reason = "minute window"
            elif wait_time == wait_for_interval and wait_for_interval > 0:
                reason = "min interval"

            if wait_time == 0.0:
                self._request_times.append(now)

            return wait_time, reason, len(self._request_times)

    async def acquire(self) -> None:
        import random
        while True:
            wait_time, reason, used_slots = self._reserve_slot()
            if wait_time == 0.0:
                jitter = random.uniform(0, 0.5)
                if jitter > 0:
                    logger.warning(
                        "[Rate Limiter] Jitter %.2fs to avoid thundering herd",
                        jitter,
                    )
                    await asyncio.sleep(jitter)

                logger.warning(
                    "[Rate Limiter] Request allowed | current window usage=%s/%s | min interval=%.2fs",
                    used_slots,
                    Config.OPENROUTER_REQUESTS_PER_MINUTE,
                    Config.MIN_REQUEST_INTERVAL,
                )
                return
            logger.warning(
                "[Rate Limiter] Waiting %.2fs | reason=%s | current window usage=%s/%s",
                wait_time,
                reason,
                used_slots,
                Config.OPENROUTER_REQUESTS_PER_MINUTE,
            )
            await asyncio.sleep(wait_time)

    def enter_cooldown(self, wait_time: float) -> None:
        cooldown = max(float(wait_time), float(Config.OPENROUTER_429_COOLDOWN_SECONDS))
        with self._lock:
            self._cooldown_until = max(self._cooldown_until, time.time() + cooldown)
            logger.warning(
                "[Rate Limiter] Set cooldown %.2fs | cooldown deadline timestamp=%.0f | current window usage=%s/%s",
                cooldown,
                self._cooldown_until,
                len(self._request_times),
                Config.OPENROUTER_REQUESTS_PER_MINUTE,
            )


_rate_limiter = OpenRouterRateLimiter()


def get_openrouter_rate_limiter() -> OpenRouterRateLimiter:
    return _rate_limiter
