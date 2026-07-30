import asyncio
import time
from collections import defaultdict


class RateLimiter:
    """Paces calls to one provider to at most `rpm` per minute.

    This state lives in the process that constructs it. `AnomalyService` is an
    `lru_cache`d singleton, so pacing holds across requests within one uvicorn
    *worker* — but if the app runs under multiple workers/processes
    (`uvicorn --workers N`, gunicorn, multiple containers), each gets its own
    instance and its own independent budget, so the *effective* RPM to a
    provider becomes `workers × rpm`, not `rpm`. Divide the configured RPM by
    the worker count if you scale out, or run this app single-worker per
    provider-key.
    """

    def __init__(self, rpm: int):
        self.min_interval = 60.0 / max(rpm, 1)
        self._last_call = 0.0

    async def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()


class InboundRateLimiter:
    """Fixed-window per-client request cap for inbound HTTP traffic.

    Same single-process caveat as `RateLimiter` above: state is per-worker, so
    the effective limit scales with worker count under multiple workers.
    """

    def __init__(self, limit_per_minute: int):
        self.limit = max(limit_per_minute, 1)
        self._window_start: dict[str, float] = defaultdict(float)
        self._count: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        now = time.monotonic()
        async with self._lock:
            if now - self._window_start[key] >= 60.0:
                self._window_start[key] = now
                self._count[key] = 0
            self._count[key] += 1
            return self._count[key] <= self.limit
