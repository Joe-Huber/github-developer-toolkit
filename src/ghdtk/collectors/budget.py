"""Request budget planner for profile collection (issue #22).

A single run gathers user + repositories + per-repo metadata + activity within
a request budget. :class:`CollectionBudget` tracks actual requests used (via
the client's counter) against a hard cap so the orchestrator can skip or abort
collections instead of burning the rate quota.
"""

from __future__ import annotations

__all__ = ["CollectionBudget"]


class CollectionBudget:
    """Tracks used requests against a hard cap."""

    def __init__(self, max_requests: int) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be at least 1")
        self._max = max_requests
        self._used = 0

    @property
    def max_requests(self) -> int:
        """The configured hard cap on requests."""
        return self._max

    @property
    def used(self) -> int:
        """Requests consumed so far."""
        return self._used

    @property
    def remaining(self) -> int:
        """Requests left before the cap."""
        return max(0, self._max - self._used)

    def consume(self, amount: int) -> None:
        """Record ``amount`` requests against the budget."""
        self._used += max(0, amount)

    def can_run(self, estimated: int = 1) -> bool:
        """Whether a collection estimated at ``estimated`` requests fits."""
        return self.used + estimated <= self._max
