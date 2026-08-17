"""Collection run metrics: timings, request counts and error counters (issue #65).

A :class:`CollectionMetrics` instance is owned by one :func:`collect_profile`
run and records wall-clock timings per collection, request usage, and error
tallies. The snapshot is a plain dict so it can be logged as structured fields
or written into a diagnostics report.

Thread safety (issue #63): parallel collectors share one metrics instance, so
every mutation is lock-guarded and the snapshot is taken under the same lock.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

__all__ = ["CollectionMetrics", "run_timed"]

T = TypeVar("T")


@dataclass
class _Timing:
    count: int = 0
    total_seconds: float = 0.0

    def add(self, seconds: float) -> None:
        self.count += 1
        self.total_seconds += seconds


class CollectionMetrics:
    """Thread-safe timing and counter registry for one collection run."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._timings: dict[str, _Timing] = {}
        self._counters: dict[str, int] = {}

    def record_timing(self, name: str, seconds: float) -> None:
        """Record a wall-clock duration under ``name``."""
        with self._lock:
            self._timings.setdefault(name, _Timing()).add(seconds)

    def increment(self, name: str, amount: int = 1) -> None:
        """Increment a named counter (used for error/status tallies)."""
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + amount

    def snapshot(self) -> dict[str, Any]:
        """Return a plain-dict snapshot safe for structured logging."""
        with self._lock:
            timings = {
                name: {
                    "count": timing.count,
                    "total_seconds": round(timing.total_seconds, 6),
                    "mean_seconds": round(timing.total_seconds / timing.count, 6)
                    if timing.count
                    else None,
                }
                for name, timing in self._timings.items()
            }
            return {"timings": timings, "counters": dict(self._counters)}


def run_timed(metrics: CollectionMetrics, name: str, operation: Callable[[], T]) -> T:
    """Run ``operation`` while recording its wall-clock duration in ``metrics``."""
    start = time.perf_counter()
    try:
        return operation()
    finally:
        metrics.record_timing(name, time.perf_counter() - start)
