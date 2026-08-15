"""Rate-limit tracking and retry backoff for the GitHub API client.

GitHub enforces hourly (primary) and secondary (abuse) rate limits. Profile
analysis makes many paginated calls, so the client must track the remaining
primary budget, pause when it is exhausted, and back off with exponential
delay + jitter on secondary 403/429 responses (issue #18).

Both policies are injectable so tests can use tiny delays and deterministic
jitter instead of sleeping for real.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from random import uniform
from time import sleep
from typing import Any

import httpx


def parse_retry_after(value: str | None) -> float | None:
    """Parse a ``Retry-After`` header (delay seconds or an HTTP date)."""
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


class RateLimitState:
    """The primary rate-limit budget reported by ``X-RateLimit-*`` headers."""

    def __init__(self) -> None:
        self.limit: int | None = None
        self.remaining: int | None = None
        self.reset_at: datetime | None = None

    def update_from(self, response: httpx.Response) -> None:
        """Update the tracked budget from a response's headers."""
        limit = response.headers.get("X-RateLimit-Limit")
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        if limit is not None:
            try:
                self.limit = int(limit)
            except ValueError:
                pass
        if remaining is not None:
            try:
                self.remaining = int(remaining)
            except ValueError:
                pass
        if reset is not None:
            try:
                self.reset_at = datetime.fromtimestamp(int(reset), tz=UTC)
            except (ValueError, OSError):
                pass

    @property
    def exhausted(self) -> bool:
        """Whether the tracked primary budget is exhausted."""
        return self.remaining is not None and self.remaining <= 0

    def wait_seconds(self, now: datetime | None = None) -> float:
        """Seconds until the primary limit resets (``0`` when not applicable)."""
        if not self.exhausted or self.reset_at is None:
            return 0.0
        now = now if now is not None else datetime.now(UTC)
        return max(0.0, (self.reset_at - now).total_seconds())

    def to_dict(self) -> dict[str, Any]:
        """Serialize the budget for diagnostics or report metadata."""
        return {
            "limit": self.limit,
            "remaining": self.remaining,
            "reset_at": self.reset_at.isoformat() if self.reset_at else None,
        }


class BackoffPolicy:
    """Exponential backoff with jitter, capped at ``max_delay`` seconds."""

    def __init__(
        self,
        *,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: float = 0.2,
        sleep_fn: Callable[[float], None] = sleep,
        random_fn: Callable[[float, float], float] = uniform,
    ) -> None:
        if base_delay < 0 or max_delay < 0 or jitter < 0:
            raise ValueError("backoff delays and jitter must be non-negative")
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self._sleep = sleep_fn
        self._random = random_fn

    def delay(self, attempt: int) -> float:
        """Compute the backoff delay for the given 1-based attempt."""
        exponential = self.base_delay * (2.0 ** (attempt - 1))
        capped = min(exponential, self.max_delay)
        factor = 1.0 + self._random(-self.jitter, self.jitter)
        return max(0.0, capped * factor)

    def sleep(self, seconds: float) -> None:
        """Sleep for ``seconds`` using the injected sleep function."""
        self._sleep(seconds)
