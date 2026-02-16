"""
Debounce utilities for controlling flush cadence.
"""

from __future__ import annotations

from collections.abc import Callable


class Debouncer:
    def __init__(self, interval_s: float, now_fn: Callable[[], float]):
        self._interval_s = interval_s
        self._now = now_fn

    def should_flush(self, last_flush_time: float) -> bool:
        return self._now() - last_flush_time >= self._interval_s

    def mark_flushed(self) -> float:
        return self._now()
