"""Request budget planner for profile collection (issue #22).

A single run gathers user + repositories + per-repo metadata + activity within
a request budget. :class:`CollectionBudget` tracks actual requests used (via
the client's counter) against a hard cap so the orchestrator can skip or abort
collections instead of burning the rate quota.

Thread safety (issue #63): collection can run several collectors in parallel,
so the budget is lock-guarded and supports *reservations*. A reservation marks
an estimated cost as in-flight *before* the work starts, which lets the planner
see parallel bursts and refuse dispatches that would collectively exceed the
cap; ``settle`` then reconciles the reservation against the actual requests
used once the work completes.
"""

from __future__ import annotations

import threading

__all__ = ["CollectionBudget"]


class CollectionBudget:
    """Tracks used requests against a hard cap, thread-safely."""

    def __init__(self, max_requests: int) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be at least 1")
        self._max = max_requests
        self._used = 0
        self._lock = threading.Lock()

    @property
    def max_requests(self) -> int:
        """The configured hard cap on requests."""
        return self._max

    @property
    def used(self) -> int:
        """Requests consumed so far (including in-flight reservations)."""
        with self._lock:
            return self._used

    @property
    def remaining(self) -> int:
        """Requests left before the cap."""
        return max(0, self._max - self.used)

    def consume(self, amount: int) -> None:
        """Record ``amount`` requests against the budget."""
        with self._lock:
            self._used += max(0, amount)

    def can_run(self, estimated: int = 1) -> bool:
        """Whether a collection estimated at ``estimated`` requests fits."""
        with self._lock:
            return self._used + estimated <= self._max

    def reserve(self, estimated: int) -> bool:
        """Atomically reserve ``estimated`` requests for in-flight work.

        Returns ``True`` and commits the reservation when it fits; ``False``
        (leaving the budget untouched) when it does not.
        """
        if estimated < 0:
            raise ValueError("estimated must be non-negative")
        with self._lock:
            if self._used + estimated > self._max:
                return False
            self._used += estimated
            return True

    def settle(self, estimated: int, used: int) -> None:
        """Reconcile a reservation against the actual requests used.

        Reserving ``estimated`` and then settling with ``used`` yields a net
        ``used`` change, so unused reservation capacity is released (a negative
        delta) and any overrun beyond the estimate is charged (a positive
        delta).
        """
        if estimated < 0 or used < 0:
            raise ValueError("estimated and used must be non-negative")
        with self._lock:
            self._used += used - estimated
