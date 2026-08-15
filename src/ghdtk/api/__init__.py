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
from ghdtk.api.normalizers import (
    CommitActivity,
    IssueStats,
    LanguageShare,
    NormalizedRepository,
    NormalizedUser,
    PullRequestStats,
    RepositorySummary,
    commit_activity,
    issue_stats,
    language_breakdown,
    normalize_repository,
    normalize_user,
    pull_request_stats,
    summarize_repositories,
    validate_sanity,
)
from ghdtk.api.pagination import has_next_page, next_page_url, parse_link_header
from ghdtk.api.rate_limit import BackoffPolicy, RateLimitState, parse_retry_after

__all__ = [
    "APITimeoutError",
    "AuthenticationError",
    "BackoffPolicy",
    "CommitActivity",
    "DataValidationError",
    "GitHubAPIError",
    "IssueStats",
    "LanguageShare",
    "MalformedResponseError",
    "NetworkError",
    "NormalizedRepository",
    "NormalizedUser",
    "NotFoundError",
    "PartialDataError",
    "PartialDataSummary",
    "PullRequestStats",
    "RateLimitError",
    "RateLimitState",
    "RepositorySummary",
    "UserNotFoundError",
    "commit_activity",
    "has_next_page",
    "issue_stats",
    "language_breakdown",
    "next_page_url",
    "normalize_repository",
    "normalize_user",
    "parse_link_header",
    "parse_retry_after",
    "pull_request_stats",
    "summarize_repositories",
    "validate_sanity",
]
