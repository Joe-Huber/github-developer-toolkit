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
from ghdtk.api.pagination import has_next_page, next_page_url, parse_link_header
from ghdtk.api.rate_limit import BackoffPolicy, RateLimitState, parse_retry_after

__all__ = [
    "APITimeoutError",
    "AuthenticationError",
    "BackoffPolicy",
    "DataValidationError",
    "GitHubAPIError",
    "MalformedResponseError",
    "NetworkError",
    "NotFoundError",
    "PartialDataError",
    "PartialDataSummary",
    "RateLimitError",
    "RateLimitState",
    "UserNotFoundError",
    "has_next_page",
    "next_page_url",
    "parse_link_header",
    "parse_retry_after",
]
