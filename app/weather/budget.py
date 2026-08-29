"""In-process guardrails for non-commercial provider request quotas."""

from __future__ import annotations

import threading
import time
import logging
from collections import deque


class ProviderBudgetExceeded(RuntimeError):
    pass


class RequestBudget:
    def __init__(self, per_minute: int = 500, per_hour: int = 4500,
                 per_day: int = 10_000, soft_stop_ratio: float = 0.8,
                 warning_ratio: float = 0.7, clock=time.monotonic) -> None:
        self._daily_limit = per_day
        self._soft_limit = max(1, int(per_day * soft_stop_ratio))
        self._warning_limit = max(1, int(per_day * warning_ratio))
        self._warned = False
        self._limits = ((60.0, per_minute), (3600.0, per_hour), (86400.0, self._soft_limit))
        self._events: deque[float] = deque()
        self._clock = clock
        self._lock = threading.Lock()

    def consume(self) -> None:
        now = self._clock()
        with self._lock:
            while self._events and self._events[0] <= now - 86400.0:
                self._events.popleft()
            for window, limit in self._limits:
                if sum(event > now - window for event in self._events) >= limit:
                    raise ProviderBudgetExceeded("weather provider request budget exhausted")
            self._events.append(now)
            if len(self._events) >= self._warning_limit and not self._warned:
                logging.getLogger(__name__).warning(
                    "weather provider daily budget reached %d%%", int(100 * len(self._events) / self._daily_limit)
                )
                self._warned = True


default_request_budget = RequestBudget()
