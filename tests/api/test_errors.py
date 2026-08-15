"""Unit tests for the GitHub API error taxonomy (issue #20).

Verifies the typed exception hierarchy, that concrete failure modes carry the
context callers need (retry advice, endpoint + record context, partial-data
summaries), and that every error can be caught via the base class.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

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


def test_every_error_is_a_github_api_error() -> None:
    errors = [
        AuthenticationError("bad token"),
        UserNotFoundError("no such user"),
        NotFoundError("no such resource"),
        RateLimitError("quota exhausted"),
        APITimeoutError("timed out"),
        NetworkError("connection refused"),
        MalformedResponseError("bad json"),
        DataValidationError("bad data", endpoint="user"),
        PartialDataError("incomplete", summary=PartialDataSummary([])),
    ]
    for error in errors:
        assert isinstance(error, GitHubAPIError)


def test_authentication_error_status_code() -> None:
    error = AuthenticationError("bad token")
    assert error.status_code == 401


def test_user_not_found_is_not_found() -> None:
    assert issubclass(UserNotFoundError, NotFoundError)
    error = UserNotFoundError("octocat does not exist")
    assert error.status_code == 404
    assert "octocat" in str(error)


def test_rate_limit_carries_retry_advice() -> None:
    reset_at = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
    error = RateLimitError(
        "secondary limit",
        status_code=429,
        retry_after=15.0,
        reset_at=reset_at,
    )
    assert error.status_code == 429
    assert error.retry_after == 15.0
    assert error.reset_at == reset_at


def test_rate_limit_without_retry_advice() -> None:
    error = RateLimitError("primary limit exhausted")
    assert error.retry_after is None
    assert error.reset_at is None


def test_data_validation_carries_context() -> None:
    error = DataValidationError(
        "stargazers_count must be non-negative",
        endpoint="repository",
        record=2,
        errors=["stargazers_count must be >= 0"],
    )
    assert error.endpoint == "repository"
    assert error.record == 2
    assert error.errors == ["stargazers_count must be >= 0"]


def test_data_validation_whole_response_has_no_record() -> None:
    error = DataValidationError("expected a dict", endpoint="languages")
    assert error.record is None
    assert error.errors == []


def test_partial_data_summary_serializes() -> None:
    summary = PartialDataSummary(
        [
            {"name": "user", "status": "complete"},
            {"name": "followers", "status": "failed", "error": "rate limited"},
        ]
    )
    assert summary.to_dict() == [
        {"name": "user", "status": "complete"},
        {"name": "followers", "status": "failed", "error": "rate limited"},
    ]


def test_partial_data_error_carries_summary() -> None:
    summary = PartialDataSummary([{"name": "readme", "status": "missing"}])
    error = PartialDataError("readme unavailable", summary=summary)
    assert error.summary.to_dict() == [{"name": "readme", "status": "missing"}]


def test_catchable_via_base_class() -> None:
    with pytest.raises(GitHubAPIError):
        raise AuthenticationError("boom")
