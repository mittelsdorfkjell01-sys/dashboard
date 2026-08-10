"""In-process guardrails for non-commercial provider request quotas."""

from __future__ import annotations

import threading
import time
from collections import deque


class ProviderBudgetExceeded(RuntimeError):
    pass


class RequestBudget:
    def __init__(self, per_minute: int = 500, per_hour: int = 4500, clock=time.monotonic) -> None:
        self._limits = ((60.0, per_minute), (3600.0, per_hour))
        self._events: deque[float] = deque()
        self._clock = clock
        self._lock = threading.Lock()

    def consume(self) -> None:
        now = self._clock()
        with self._lock:
            while self._events and self._events[0] <= now - 3600.0:
                self._events.popleft()
            for window, limit in self._limits:
                if sum(event > now - window for event in self._events) >= limit:
                    raise ProviderBudgetExceeded("weather provider request budget exhausted")
            self._events.append(now)


default_request_budget = RequestBudget()
