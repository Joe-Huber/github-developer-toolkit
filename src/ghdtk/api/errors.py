"""Typed error taxonomy for the GitHub API data layer.

Distinct failure modes need distinct handling so that analysis and UX can
respond appropriately (issue #20). The taxonomy mirrors the failure modes the
data layer can actually encounter:

- authentication / authorization failures
- user-not-found (and generic not-found)
- primary and secondary rate limits
- timeouts and network errors
- malformed responses
- data validation failures (field-level vs whole-response)
- partial data

Callers catch the concrete subclass and decide whether to abort or degrade;
the CLI can map each class to human-readable guidance, and the report layer can
serialize partial-data summaries where relevant.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any


class GitHubAPIError(Exception):
    """Base class for every typed error raised by the data layer.

    ``status_code`` is the HTTP status code that caused the error when one is
    known, otherwise ``None``.
    """

    status_code: int | None = None


class AuthenticationError(GitHubAPIError):
    """Authentication or authorization failed (401, or 403 without scope)."""

    status_code = 401


class NotFoundError(GitHubAPIError):
    """A requested resource does not exist (404)."""

    status_code = 404


class UserNotFoundError(NotFoundError):
    """A GitHub user does not exist (404 on a user endpoint)."""


class RateLimitError(GitHubAPIError):
    """A primary or secondary rate limit was exhausted.

    ``retry_after`` is the recommended wait in seconds when the API provided
    one (``Retry-After`` header); ``reset_at`` is the primary-limit reset time
    when it was reported (``X-RateLimit-Reset`` header).
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after: float | None = None,
        reset_at: datetime | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after
        self.reset_at = reset_at


class APITimeoutError(GitHubAPIError):
    """A request timed out."""


class NetworkError(GitHubAPIError):
    """Transport-level failure (DNS, connection refused, TLS, etc.)."""


class MalformedResponseError(GitHubAPIError):
    """A response could not be interpreted.

    Raised when the body is not valid JSON or does not have the shape the
    endpoint is expected to return (whole-response failure).
    """


class DataValidationError(GitHubAPIError):
    """A response parsed but failed data validation.

    ``endpoint`` names the API endpoint, ``record`` the index within a page
    (or ``None`` for whole-response failures), and ``errors`` the
    human-readable validation problems.
    """

    def __init__(
        self,
        message: str,
        *,
        endpoint: str,
        record: int | None = None,
        errors: Iterable[str] = (),
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.endpoint = endpoint
        self.record = record
        self.errors = list(errors)
        self.status_code = status_code


class PartialDataSummary:
    """Serializable summary of what a partial collection was able to gather.

    Collectors report which collections succeeded and which were skipped or
    failed so a ``collect_profile`` run can return a clearly-marked partial
    snapshot instead of crashing (issue #20 / #22).
    """

    def __init__(self, collections: Iterable[dict[str, Any]]) -> None:
        self.collections = list(collections)

    def to_dict(self) -> list[dict[str, Any]]:
        """Return the summary as plain JSON-serializable data."""
        return self.collections


class PartialDataError(GitHubAPIError):
    """A collection finished with missing pieces.

    ``summary`` carries per-collection status; the report layer can serialize
    it where relevant.
    """

    def __init__(self, message: str, *, summary: PartialDataSummary) -> None:
        super().__init__(message)
        self.summary = summary


__all__ = [
    "APITimeoutError",
    "AuthenticationError",
    "DataValidationError",
    "GitHubAPIError",
    "MalformedResponseError",
    "NetworkError",
    "NotFoundError",
    "PartialDataError",
    "PartialDataSummary",
    "RateLimitError",
    "UserNotFoundError",
]
