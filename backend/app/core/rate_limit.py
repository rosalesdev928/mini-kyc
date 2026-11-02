"""Small in-memory sliding-window rate limiter and the FastAPI dependencies that use it.

It protects a single instance (which is what the free hosting runs). With several instances each one would keep
its own counters; a real deployment would use a shared store such as Redis or the platform's rate limiting.
The client IP comes from the first `X-Forwarded-For` entry (the hosting proxy sets it), so a determined client can
spoof it: this is a guard against accidents, scripts and quota exhaustion, not a security boundary on its own.
"""

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

from fastapi import Request

from app.core.config import Settings
from app.core.errors import TooManyRequestsError


class SlidingWindowLimiter:
    """Allows `limit` events per `window_seconds` for each key. `limit <= 0` disables the limiter."""

    _MAX_KEYS = 10_000  # safety net so that the memory cannot grow without bound

    def __init__(self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic):
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._limit > 0

    def retry_after(self, key: str) -> float:
        """Seconds until `key` may act again (0.0 when it may act now). Does not record anything."""
        if not self.enabled:
            return 0.0
        with self._lock:
            events = self._fresh(key)
            if len(events) < self._limit:
                return 0.0
            return max(0.0, events[0] + self._window - self._clock())

    def record(self, key: str) -> None:
        """Count one event for `key`."""
        if not self.enabled:
            return
        with self._lock:
            self._fresh(key).append(self._clock())
            if len(self._events) > self._MAX_KEYS:
                self._drop_idle_keys()

    def acquire(self, key: str) -> float:
        """Record an event if `key` is under the limit. Returns 0.0 on success, else the seconds to wait."""
        wait = self.retry_after(key)
        if wait == 0.0:
            self.record(key)
        return wait

    def clear(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

    def _fresh(self, key: str) -> deque[float]:
        events = self._events.setdefault(key, deque())
        cutoff = self._clock() - self._window
        while events and events[0] <= cutoff:
            events.popleft()
        return events

    def _drop_idle_keys(self) -> None:
        cutoff = self._clock() - self._window
        for key in [k for k, events in self._events.items() if not events or events[-1] <= cutoff]:
            del self._events[key]


@dataclass(frozen=True)
class Limiters:
    uploads: SlidingWindowLimiter
    history: SlidingWindowLimiter
    admin_failures: SlidingWindowLimiter


def build_limiters(settings: Settings) -> Limiters:
    return Limiters(
        uploads=SlidingWindowLimiter(settings.rate_limit_uploads_per_minute, 60),
        history=SlidingWindowLimiter(settings.rate_limit_history_per_minute, 60),
        admin_failures=SlidingWindowLimiter(
            settings.rate_limit_admin_failures, settings.rate_limit_admin_window_seconds
        ),
    )


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    if first:
        return first[:64]
    return request.client.host if request.client else "unknown"


def _too_many(wait: float) -> TooManyRequestsError:
    seconds = max(1, int(wait) + 1)
    return TooManyRequestsError(
        f"Too many requests. Please try again in {seconds} seconds.", retry_after_seconds=seconds
    )


def limit_uploads(request: Request) -> None:
    wait = request.app.state.limiters.uploads.acquire(client_ip(request))
    if wait:
        raise _too_many(wait)


def limit_history(request: Request) -> None:
    wait = request.app.state.limiters.history.acquire(client_ip(request))
    if wait:
        raise _too_many(wait)
