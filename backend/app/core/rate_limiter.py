import asyncio
import time


class RateLimiter:
    def __init__(self, rpm: int):
        self.min_interval = 60.0 / max(rpm, 1)
        self._last_call = 0.0

    async def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()
