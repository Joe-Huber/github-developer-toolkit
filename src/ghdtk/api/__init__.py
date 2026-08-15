"""GitHub API client layer.

Responsible for talking to the GitHub REST/GraphQL APIs, authentication, rate
limit handling, retries, and returning typed raw payloads for the collectors.
Collectors turn these payloads into :mod:`ghdtk.models.raw` snapshots.

The typed failure taxonomy (:mod:`ghdtk.api.errors`) lets callers catch
concrete failure modes — auth, user-not-found, rate limits, timeouts, network,
malformed responses and partial data — and decide whether to abort or degrade.
"""

from ghdtk.api.errors import (
    APITimeoutError,
    AuthenticationError,
    DataValidationError,
    GitHubAPIError,
    MalformedResponseError,
    NetworkError,
    NotFoundError,
    PartialDataError,
    PartialDataSummary,
    RateLimitError,
    UserNotFoundError,
)

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
