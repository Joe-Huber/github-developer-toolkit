"""Property-based tests for the normalization layer (issue #60).

These complement the directed unit tests in ``test_normalizers.py`` by checking
mathematical invariants over many randomly generated payloads: shares sum to
one, aggregations are consistent with their inputs, derived timings are
non-negative, and per-field flags agree with the raw fields they summarize.
"""

from __future__ import annotations

import statistics
from datetime import UTC, datetime
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ghdtk.api.normalizers import (
    CommitActivity,
    IssueStats,
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
)
from ghdtk.models.raw import (
    Commit,
    CommitDetail,
    GitUser,
    Issue,
    LanguageStats,
    PullRequest,
    Repository,
    User,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

_language_names = st.sampled_from(["Python", "TypeScript", "Rust", "Go", "C", "Ruby", "N/A"])


@st.composite
def language_stats(draw: Any) -> LanguageStats:
    counts = draw(st.lists(st.integers(min_value=0, max_value=10**6), min_size=0, max_size=8))
    names = draw(
        st.lists(_language_names, min_size=len(counts), max_size=len(counts)).filter(
            lambda xs: len(set(xs)) == len(xs)
        )
    )
    return LanguageStats(dict(zip(names, counts, strict=True)))


@st.composite
def repositories(draw: Any) -> list[Repository]:
    count = draw(st.integers(min_value=0, max_value=6))
    return [
        Repository(
            full_name=f"owner/repo-{index}",
            name=f"repo-{index}",
            stargazers_count=draw(st.integers(min_value=0, max_value=5000)),
            forks_count=draw(st.integers(min_value=0, max_value=1000)),
            language=draw(st.one_of(st.none(), _language_names)),
            fork=draw(st.booleans()),
            archived=draw(st.booleans()),
            created_at=draw(st.one_of(st.none(), st.datetimes())),
            pushed_at=draw(st.one_of(st.none(), st.datetimes())),
        )
        for index in range(count)
    ]


@st.composite
def commits(draw: Any) -> list[Commit]:
    count = draw(st.integers(min_value=0, max_value=6))
    logins = draw(st.lists(st.text(max_size=8), min_size=1, max_size=4))
    return [
        Commit(
            sha=f"abc123{index}",
            author=(
                User(login=draw(st.sampled_from(logins)), id=index) if draw(st.booleans()) else None
            ),
            commit=CommitDetail(
                author=GitUser(
                    name=draw(st.text(max_size=8)),
                    email=draw(st.text(max_size=16)),
                    date=draw(st.datetimes()),
                )
            ),
        )
        for index in range(count)
    ]


@st.composite
def issues(draw: Any) -> list[Issue]:
    count = draw(st.integers(min_value=0, max_value=6))
    return [
        Issue(
            number=index,
            title="issue",
            state=draw(st.sampled_from(["open", "closed"])),
            created_at=draw(st.datetimes()),
            closed_at=draw(st.datetimes()) if draw(st.booleans()) else None,
        )
        for index in range(count)
    ]


@st.composite
def pull_requests(draw: Any) -> list[PullRequest]:
    count = draw(st.integers(min_value=0, max_value=6))
    return [
        PullRequest(
            number=index,
            title="pr",
            state=draw(st.sampled_from(["open", "closed"])),
            merged=draw(st.booleans()),
            created_at=draw(st.datetimes()),
            merged_at=draw(st.datetimes()) if draw(st.booleans()) else None,
        )
        for index in range(count)
    ]


@settings(max_examples=50, deadline=None)
@given(language_stats())
def test_language_breakdown_shares_are_well_formed(stats: LanguageStats) -> None:
    shares = language_breakdown(stats)
    total = stats.total_bytes
    if total <= 0:
        assert shares == []
        return
    assert shares
    assert all(0.0 <= share.share <= 1.0 for share in shares)
    assert [share.language for share in shares] == [name for name, _ in stats.top_languages]
    assert sum(share.share for share in shares) == pytest.approx(1.0)
    assert sum(share.bytes for share in shares) == total


@settings(max_examples=50, deadline=None)
@given(language_stats(), st.integers(min_value=0, max_value=10))
def test_language_breakdown_limit_truncates_and_preserves_order(
    stats: LanguageStats, limit: int
) -> None:
    shares = language_breakdown(stats, limit=limit)
    total = stats.total_bytes
    if total <= 0:
        assert shares == []
        return
    assert len(shares) == min(limit, len(stats.top_languages))
    assert sum(share.share for share in shares) <= 1.0
    if shares:
        assert shares[0].language == stats.top_languages[0][0]


@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=0, max_value=5000), st.integers(min_value=0, max_value=5000))
def test_language_breakdown_largest_share_dominates(extra: int, base: int) -> None:
    stats = LanguageStats({"Python": base + extra, "Rust": base})
    shares = language_breakdown(stats)
    if stats.total_bytes <= 0:
        assert shares == []
        return
    assert shares[0].language == "Python"
    assert shares[0].share >= 0.5


@settings(max_examples=50, deadline=None)
@given(repositories())
def test_summarize_repositories_is_consistent_with_input(repos: list[Repository]) -> None:
    summary = summarize_repositories(repos, now=NOW)
    assert summary.considered_repositories == len(repos)
    assert summary.total_stars == sum(repo.stargazers_count or 0 for repo in repos)
    assert summary.total_forks == sum(repo.forks_count or 0 for repo in repos)
    if repos:
        assert summary.average_stars == pytest.approx(summary.total_stars / len(repos))
        assert summary.median_stars == pytest.approx(
            statistics.median([repo.stargazers_count or 0 for repo in repos])
        )
    else:
        assert summary.average_stars == 0.0
        assert summary.median_stars == 0.0
        assert summary.top_language is None
    assert summary.archived_count == sum(1 for repo in repos if repo.archived)
    assert summary.forked_count == sum(1 for repo in repos if repo.fork)
    if summary.top_language is not None:
        languages = {repo.language for repo in repos if repo.language}
        assert summary.top_language in languages


@settings(max_examples=50, deadline=None)
@given(repositories(), st.integers(min_value=0, max_value=2500))
def test_summarize_repositories_min_stars_filters(repos: list[Repository], min_stars: int) -> None:
    summary = summarize_repositories(repos, min_stars=min_stars, now=NOW)
    considered = [repo for repo in repos if (repo.stargazers_count or 0) >= min_stars]
    assert summary.considered_repositories == len(considered)
    assert summary.total_stars == sum(repo.stargazers_count or 0 for repo in considered)
    assert all((repo.stargazers_count or 0) >= min_stars for repo in considered)


@settings(max_examples=50, deadline=None)
@given(st.one_of(st.none(), st.text()), st.one_of(st.none(), st.text()))
def test_normalize_user_display_name_and_flags(name: str | None, bio: str | None) -> None:
    user = User(login="l-ogi", name=name, bio=bio, created_at=datetime(2020, 1, 1, tzinfo=UTC))
    normalized = normalize_user(user, now=NOW)
    assert isinstance(normalized, NormalizedUser)
    assert normalized.display_name == (name or user.login)
    assert normalized.has_bio == bool(bio and bio.strip())
    assert normalized.account_age_days is not None and normalized.account_age_days >= 0


@settings(max_examples=50, deadline=None)
@given(st.one_of(st.none(), st.datetimes()))
def test_normalize_user_age_is_non_negative(created_at: datetime | None) -> None:
    user = User(login="l-ogi", created_at=created_at)
    normalized = normalize_user(user, now=NOW)
    if created_at is None:
        assert normalized.account_age_days is None
    else:
        assert normalized.account_age_days is not None and normalized.account_age_days >= 0


@settings(max_examples=50, deadline=None)
@given(st.one_of(st.none(), st.datetimes()), st.one_of(st.none(), st.datetimes()))
def test_normalize_repository_timings_are_non_negative(
    created_at: datetime | None, pushed_at: datetime | None
) -> None:
    repo = Repository(full_name="o/r", created_at=created_at, pushed_at=pushed_at)
    normalized = normalize_repository(repo, now=NOW)
    assert isinstance(normalized, NormalizedRepository)
    if created_at is None:
        assert normalized.age_days is None
    else:
        assert normalized.age_days is not None and normalized.age_days >= 0
    if pushed_at is None and repo.updated_at is None:
        assert normalized.staleness_days is None
    else:
        assert normalized.staleness_days is not None and normalized.staleness_days >= 0


@settings(max_examples=50, deadline=None)
@given(commits())
def test_commit_activity_is_consistent(commits_list: list[Commit]) -> None:
    activity = commit_activity(commits_list, now=NOW)
    assert isinstance(activity, CommitActivity)
    assert activity.total_commits == len(commits_list)
    assert 0 <= activity.authored_commits <= activity.total_commits
    assert activity.unique_days >= 0
    if activity.first_commit_at is not None and activity.last_commit_at is not None:
        assert activity.first_commit_at <= activity.last_commit_at
    assert activity.recency_days is None or activity.recency_days >= 0


@settings(max_examples=50, deadline=None)
@given(issues())
def test_issue_stats_counts_are_bounded(issues_list: list[Issue]) -> None:
    stats = issue_stats(issues_list, now=NOW)
    assert isinstance(stats, IssueStats)
    assert stats.total == len(issues_list)
    assert 0 <= stats.open <= stats.total
    assert 0 <= stats.closed <= stats.total
    assert stats.open + stats.closed <= stats.total
    assert stats.median_close_days is None or stats.median_close_days >= 0
    assert stats.oldest_open_days is None or stats.oldest_open_days >= 0


@settings(max_examples=50, deadline=None)
@given(pull_requests())
def test_pull_request_stats_counts_are_bounded(pulls_list: list[PullRequest]) -> None:
    stats = pull_request_stats(pulls_list, now=NOW)
    assert isinstance(stats, PullRequestStats)
    assert stats.total == len(pulls_list)
    assert 0 <= stats.open <= stats.total
    assert 0 <= stats.merged <= stats.total
    assert 0 <= stats.closed <= stats.total
    assert stats.median_merge_days is None or stats.median_merge_days >= 0
    assert stats.oldest_open_days is None or stats.oldest_open_days >= 0


@settings(max_examples=50, deadline=None)
@given(repositories())
def test_summary_derived_counts_are_integers(repos: list[Repository]) -> None:
    summary = summarize_repositories(repos, now=NOW)
    assert isinstance(summary, RepositorySummary)
    for value in (
        summary.total_stars,
        summary.total_forks,
        summary.considered_repositories,
        summary.forked_count,
        summary.archived_count,
    ):
        assert isinstance(value, int) and value >= 0
