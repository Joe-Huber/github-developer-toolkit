"""Unit tests for the data normalization and validation layer (issue #19)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ghdtk.api.errors import DataValidationError
from ghdtk.api.normalizers import (
    commit_activity,
    issue_stats,
    language_breakdown,
    normalize_repository,
    normalize_user,
    pull_request_stats,
    summarize_repositories,
    validate_sanity,
)
from ghdtk.models.raw import (
    BaseRawModel,
    Commit,
    CommitDetail,
    GitUser,
    Issue,
    LanguageStats,
    PullRequest,
    Readme,
    Repository,
    User,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _days_until(value: datetime) -> int:
    return (NOW - value).days


# --- validate_sanity ---------------------------------------------------------


def test_validate_sanity_passes_for_valid_model() -> None:
    validate_sanity(User(login="octocat", followers=5))


def test_validate_sanity_missing_required_field_raises() -> None:
    with pytest.raises(DataValidationError) as excinfo:
        validate_sanity(Readme(name=None))
    assert any("required" in error for error in excinfo.value.errors)


def test_validate_sanity_negative_count_raises() -> None:
    repo = Repository.model_validate({"full_name": "a/b", "stargazers_count": -5})
    with pytest.raises(DataValidationError) as excinfo:
        validate_sanity(repo)
    assert any("non-negative" in error for error in excinfo.value.errors)


def test_validate_sanity_unknown_model_is_noop() -> None:
    class CustomModel(BaseRawModel):
        value: int = 1

    validate_sanity(CustomModel())


def test_validate_sanity_valid_contribution_calendar() -> None:
    from ghdtk.models.raw import ContributionCalendar

    validate_sanity(ContributionCalendar(total_contributions=100))


# --- normalize_user -----------------------------------------------------------


def test_normalize_user_uses_name_or_login() -> None:
    user = User(
        login="octocat",
        name="The Octocat",
        bio="  ",
        company="GitHub",
        created_at=datetime(2020, 6, 1, tzinfo=UTC),
    )
    normalized = normalize_user(user, now=NOW)
    assert normalized.login == "octocat"
    assert normalized.display_name == "The Octocat"
    assert normalized.account_age_days == _days_until(datetime(2020, 6, 1, tzinfo=UTC))
    assert normalized.has_bio is False
    assert normalized.has_company is True
    assert normalized.has_location is False
    assert normalized.hireable is None


def test_normalize_user_login_fallback() -> None:
    normalized = normalize_user(User(login="octocat"), now=NOW)
    assert normalized.display_name == "octocat"
    assert normalized.account_age_days is None


# --- normalize_repository -------------------------------------------------------


def test_normalize_repository_derived_values() -> None:
    repo = Repository.model_validate(
        {
            "full_name": "octocat/Hello-World",
            "name": "Hello-World",
            "description": "  A demo repo  ",
            "language": "Python",
            "stargazers_count": 80,
            "forks_count": 9,
            "archived": False,
            "fork": False,
            "topics": ["demo", "api"],
            "created_at": "2020-06-01T00:00:00Z",
            "pushed_at": "2025-12-01T00:00:00Z",
        }
    )
    normalized = normalize_repository(repo, now=NOW)
    assert normalized.full_name == "octocat/Hello-World"
    assert normalized.stars == 80
    assert normalized.forks == 9
    assert normalized.topics == ("demo", "api")
    assert normalized.age_days == _days_until(datetime(2020, 6, 1, tzinfo=UTC))
    assert normalized.staleness_days == _days_until(datetime(2025, 12, 1, tzinfo=UTC))
    assert normalized.has_description is True


def test_normalize_repository_missing_counts_default_to_zero() -> None:
    repo = Repository(full_name="a/b", name="b", archived=True, fork=True)
    normalized = normalize_repository(repo, now=NOW)
    assert normalized.stars == 0
    assert normalized.forks == 0
    assert normalized.archived is True
    assert normalized.fork is True
    assert normalized.has_description is False
    assert normalized.age_days is None
    assert normalized.staleness_days is None


# --- language_breakdown ----------------------------------------------------------


def test_language_breakdown_shares() -> None:
    stats = LanguageStats({"Python": 300, "Go": 100})
    shares = language_breakdown(stats)
    assert [s.language for s in shares] == ["Python", "Go"]
    assert shares[0].share == pytest.approx(0.75)
    assert shares[1].share == pytest.approx(0.25)


def test_language_breakdown_limit_and_empty() -> None:
    stats = LanguageStats({"Python": 300, "Go": 100})
    assert len(language_breakdown(stats, limit=1)) == 1
    assert language_breakdown(LanguageStats({})) == []


# --- summarize_repositories -------------------------------------------------------


def _repo(
    full_name: str,
    *,
    stars: int,
    language: str,
    forks: int = 0,
    created: str | None = None,
    pushed: str | None = None,
    **overrides: object,
) -> Repository:
    payload: dict[str, object] = {
        "full_name": full_name,
        "name": full_name.split("/")[1],
        "stargazers_count": stars,
        "forks_count": forks,
        "language": language,
    }
    if created is not None:
        payload["created_at"] = created
    if pushed is not None:
        payload["pushed_at"] = pushed
    payload.update(overrides)
    return Repository.model_validate(payload)


def test_summarize_repositories_filters_and_aggregates() -> None:
    repos = [
        _repo(
            "a/one",
            stars=50,
            language="Python",
            forks=5,
            created="2020-01-01T00:00:00Z",
            pushed="2025-01-01T00:00:00Z",
        ),
        _repo(
            "b/two",
            stars=20,
            language="Python",
            forks=2,
            created="2021-01-01T00:00:00Z",
            pushed="2025-06-01T00:00:00Z",
            archived=True,
        ),
        _repo("c/three", stars=0, language="Go", fork=True, created="2022-01-01T00:00:00Z"),
    ]
    summary = summarize_repositories(repos, min_stars=10, now=NOW)
    assert summary.considered_repositories == 2
    assert summary.total_stars == 70
    assert summary.total_forks == 7
    assert summary.average_stars == 35.0
    assert summary.median_stars == 35.0
    assert summary.top_language == "Python"
    assert summary.language_counts == {"Python": 2}
    assert summary.forked_count == 0
    assert summary.archived_count == 1
    assert summary.oldest_repository == "a/one"
    assert summary.newest_repository == "b/two"
    assert summary.stalest_repository == "b/two"


def test_summarize_repositories_empty() -> None:
    summary = summarize_repositories([], min_stars=10, now=NOW)
    assert summary.considered_repositories == 0
    assert summary.total_stars == 0
    assert summary.average_stars == 0.0
    assert summary.median_stars == 0.0
    assert summary.top_language is None
    assert summary.oldest_repository is None


# --- commit_activity ----------------------------------------------------------------


def _commit(sha: str, *, login: str, date: str, email: str = "user@example.com") -> Commit:
    return Commit(
        sha=sha,
        author=User(login=login),
        commit=CommitDetail(
            author=GitUser(
                name=login,
                email=email,
                date=datetime.fromisoformat(date.replace("Z", "+00:00")),
            )
        ),
    )


def test_commit_activity_filters_by_author() -> None:
    commits = [
        _commit("a", login="octocat", date="2025-01-01T00:00:00Z"),
        _commit("b", login="torvalds", date="2025-02-01T00:00:00Z"),
        _commit("c", login="octocat", date="2025-03-01T00:00:00Z"),
    ]
    activity = commit_activity(commits, author_login="octocat", now=NOW)
    assert activity.total_commits == 3
    assert activity.authored_commits == 2
    assert activity.first_commit_at == datetime(2025, 1, 1, tzinfo=UTC)
    assert activity.last_commit_at == datetime(2025, 3, 1, tzinfo=UTC)
    assert activity.unique_days == 2
    assert activity.recency_days == _days_until(datetime(2025, 3, 1, tzinfo=UTC))


def test_commit_activity_no_filter_counts_all() -> None:
    commits = [
        _commit("a", login="octocat", date="2025-01-01T00:00:00Z"),
        _commit("b", login="torvalds", date="2025-02-01T00:00:00Z"),
    ]
    activity = commit_activity(commits, now=NOW)
    assert activity.authored_commits == 2
    assert activity.unique_days == 2


def test_commit_activity_empty() -> None:
    activity = commit_activity([], now=NOW)
    assert activity.total_commits == 0
    assert activity.first_commit_at is None
    assert activity.recency_days is None


# --- issue_stats -----------------------------------------------------------------------


def _issue(
    number: int,
    *,
    state: str,
    login: str,
    created: str,
    closed: str | None = None,
) -> Issue:
    return Issue(
        number=number,
        title=f"issue {number}",
        state=state,
        user=User(login=login),
        created_at=datetime.fromisoformat(created.replace("Z", "+00:00")),
        closed_at=datetime.fromisoformat(closed.replace("Z", "+00:00")) if closed else None,
    )


def test_issue_stats_lifecycle() -> None:
    issues = [
        _issue(1, state="open", login="octocat", created="2025-01-01T00:00:00Z"),
        _issue(
            2,
            state="closed",
            login="octocat",
            created="2025-01-10T00:00:00Z",
            closed="2025-01-12T00:00:00Z",
        ),
        _issue(
            3,
            state="closed",
            login="octocat",
            created="2025-02-01T00:00:00Z",
            closed="2025-02-10T00:00:00Z",
        ),
    ]
    stats = issue_stats(issues, now=NOW)
    assert stats.total == 3
    assert stats.open == 1
    assert stats.closed == 2
    assert stats.median_close_days == 5.5
    assert stats.oldest_open_days == _days_until(datetime(2025, 1, 1, tzinfo=UTC))


def test_issue_stats_author_filter_and_empty() -> None:
    issues = [_issue(1, state="open", login="octocat", created="2025-01-01T00:00:00Z")]
    stats = issue_stats(issues, author_login="torvalds", now=NOW)
    assert stats.total == 0
    assert stats.median_close_days is None
    assert stats.oldest_open_days is None


# --- pull_request_stats ------------------------------------------------------------------


def _pull(
    number: int,
    *,
    state: str,
    login: str,
    created: str,
    merged_at: str | None = None,
) -> PullRequest:
    return PullRequest(
        number=number,
        title=f"pull {number}",
        state=state,
        user=User(login=login),
        merged=merged_at is not None,
        created_at=datetime.fromisoformat(created.replace("Z", "+00:00")),
        merged_at=datetime.fromisoformat(merged_at.replace("Z", "+00:00")) if merged_at else None,
    )


def test_pull_request_stats_lifecycle() -> None:
    pulls = [
        _pull(1, state="open", login="octocat", created="2025-01-01T00:00:00Z"),
        _pull(
            2,
            state="closed",
            login="octocat",
            created="2025-02-01T00:00:00Z",
            merged_at="2025-02-05T00:00:00Z",
        ),
        _pull(3, state="closed", login="octocat", created="2025-03-01T00:00:00Z"),
    ]
    stats = pull_request_stats(pulls, now=NOW)
    assert stats.total == 3
    assert stats.open == 1
    assert stats.closed == 2
    assert stats.merged == 1
    assert stats.median_merge_days == 4.0
    assert stats.oldest_open_days == _days_until(datetime(2025, 1, 1, tzinfo=UTC))


def test_pull_request_stats_author_filter() -> None:
    pulls = [
        _pull(1, state="open", login="octocat", created="2025-01-01T00:00:00Z"),
        _pull(2, state="open", login="torvalds", created="2025-06-01T00:00:00Z"),
    ]
    stats = pull_request_stats(pulls, author_login="octocat", now=NOW)
    assert stats.total == 1
    assert stats.oldest_open_days == _days_until(datetime(2025, 1, 1, tzinfo=UTC))
