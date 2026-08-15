"""Data normalization and validation layer (issue #19).

REST/GraphQL payloads vary in casing, optional fields, and nulls. The raw
models (issues #12/#14) already coerce types and ISO dates; this module adds
the "is the data usable" rules the raw models intentionally leave open:

- ``validate_sanity`` enforces required fields and non-negative counts per
  entity. Raw models allow any ``int``, so a payload with ``followers: -5``
  would otherwise pass silently.
- The ``normalize_*`` / ``summarize_*`` helpers map raw snapshots into
  analysis-ready structures with explicit defaults and derived fields (account
  age, repository staleness, language shares, commit activity windows).

Failures raise :class:`~ghdtk.api.errors.DataValidationError` so callers can
classify a response as unusable rather than fabricating data.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import median
from typing import Any

from pydantic import BaseModel, ConfigDict

from ghdtk.api.errors import DataValidationError
from ghdtk.models.raw import (
    BaseRawModel,
    Commit,
    ContributionCalendar,
    Follower,
    Issue,
    LanguageStats,
    PullRequest,
    Readme,
    Repository,
    Stargazer,
    User,
)


@dataclass(frozen=True)
class ValidationRules:
    """Validation requirements for one raw entity."""

    required: tuple[str, ...]
    non_negative: tuple[str, ...]


_VALIDATION_RULES: dict[type[BaseRawModel], ValidationRules] = {
    User: ValidationRules(
        required=("login",),
        non_negative=("public_repos", "public_gists", "followers", "following"),
    ),
    Repository: ValidationRules(
        required=("full_name",),
        non_negative=(
            "stargazers_count",
            "watchers_count",
            "forks_count",
            "open_issues_count",
            "size",
            "forks",
            "open_issues",
            "watchers",
        ),
    ),
    Commit: ValidationRules(
        required=("sha",),
        non_negative=("commit.comment_count",),
    ),
    Follower: ValidationRules(required=("login",), non_negative=("id",)),
    Stargazer: ValidationRules(required=("login",), non_negative=("id",)),
    Issue: ValidationRules(
        required=("number", "title"),
        non_negative=("comments",),
    ),
    PullRequest: ValidationRules(
        required=("number", "title"),
        non_negative=(
            "comments",
            "review_comments",
            "commits",
            "additions",
            "deletions",
            "changed_files",
        ),
    ),
    Readme: ValidationRules(required=("name",), non_negative=("size",)),
    ContributionCalendar: ValidationRules(
        required=("total_contributions",),
        non_negative=("total_contributions",),
    ),
}


def _get_path(model: BaseRawModel, path: str) -> Any:
    value: Any = model
    for part in path.split("."):
        value = getattr(value, part)
    return value


def validate_sanity(model: BaseRawModel, *, endpoint: str = "unknown") -> None:
    """Enforce required-field and non-negative-count rules for a raw entity.

    Raises :class:`~ghdtk.api.errors.DataValidationError` when the model is
    missing a required field or carries a negative count.
    """
    rules = _VALIDATION_RULES.get(type(model))
    if rules is None:
        return
    errors: list[str] = []
    for path in rules.required:
        if _get_path(model, path) is None:
            errors.append(f"missing required field {path}")
    for path in rules.non_negative:
        value = _get_path(model, path)
        if isinstance(value, int) and value < 0:
            errors.append(f"field {path} must be non-negative, got {value}")
    if errors:
        raise DataValidationError(
            f"Unusable {type(model).__name__} payload from {endpoint}",
            endpoint=endpoint,
            errors=errors,
        )


# --- derived normalized models ---------------------------------------------


class NormalizedUser(BaseModel):
    """A profile's account fields, normalized for analysis."""

    model_config = ConfigDict(frozen=True)

    login: str
    display_name: str
    account_age_days: int | None
    has_bio: bool
    has_company: bool
    has_location: bool
    hireable: bool | None


class NormalizedRepository(BaseModel):
    """A repository's analysis-facing fields with derived timing values."""

    model_config = ConfigDict(frozen=True)

    full_name: str
    name: str
    description: str | None
    primary_language: str | None
    stars: int
    forks: int
    archived: bool
    fork: bool
    created_at: datetime | None
    pushed_at: datetime | None
    topics: tuple[str, ...]
    age_days: int | None
    staleness_days: int | None
    has_description: bool


class LanguageShare(BaseModel):
    """One language's contribution to a repository's codebase."""

    model_config = ConfigDict(frozen=True)

    language: str
    bytes: int
    share: float


class RepositorySummary(BaseModel):
    """Aggregate metrics across a user's repositories."""

    model_config = ConfigDict(frozen=True)

    considered_repositories: int
    total_stars: int
    total_forks: int
    average_stars: float
    median_stars: float
    top_language: str | None
    language_counts: dict[str, int]
    forked_count: int
    archived_count: int
    oldest_repository: str | None
    newest_repository: str | None
    stalest_repository: str | None


class CommitActivity(BaseModel):
    """Commit volume and activity window for a set of commits."""

    model_config = ConfigDict(frozen=True)

    total_commits: int
    authored_commits: int
    first_commit_at: datetime | None
    last_commit_at: datetime | None
    unique_days: int
    recency_days: int | None


class IssueStats(BaseModel):
    """Lifecycle statistics for a set of issues."""

    model_config = ConfigDict(frozen=True)

    total: int
    open: int
    closed: int
    median_close_days: float | None
    oldest_open_days: int | None


class PullRequestStats(BaseModel):
    """Lifecycle statistics for a set of pull requests."""

    model_config = ConfigDict(frozen=True)

    total: int
    open: int
    closed: int
    merged: int
    median_merge_days: float | None
    oldest_open_days: int | None


# --- helpers ----------------------------------------------------------------


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _days_between(later: datetime, earlier: datetime) -> int:
    return max(0, int((_ensure_utc(later) - _ensure_utc(earlier)).total_seconds() // 86400))


# --- per-entity normalizers --------------------------------------------------


def normalize_user(user: User, *, now: datetime | None = None) -> NormalizedUser:
    """Normalize a user snapshot into analysis-ready account fields."""
    now = now or datetime.now(UTC)
    account_age_days = _days_between(now, user.created_at) if user.created_at else None
    return NormalizedUser(
        login=user.login,
        display_name=user.name or user.login,
        account_age_days=account_age_days,
        has_bio=bool(user.bio and user.bio.strip()),
        has_company=bool(user.company and user.company.strip()),
        has_location=bool(user.location and user.location.strip()),
        hireable=user.hireable,
    )


def normalize_repository(
    repo: Repository,
    *,
    now: datetime | None = None,
) -> NormalizedRepository:
    """Normalize a repository snapshot with derived age/staleness values."""
    now = now or datetime.now(UTC)
    created = _ensure_utc(repo.created_at) if repo.created_at else None
    pushed = repo.pushed_at or repo.updated_at
    pushed = _ensure_utc(pushed) if pushed else None
    return NormalizedRepository(
        full_name=repo.full_name or "",
        name=repo.name or "",
        description=repo.description,
        primary_language=repo.language,
        stars=repo.stargazers_count or 0,
        forks=repo.forks_count or 0,
        archived=bool(repo.archived),
        fork=bool(repo.fork),
        created_at=repo.created_at,
        pushed_at=repo.pushed_at,
        topics=tuple(repo.topics or ()),
        age_days=_days_between(now, created) if created else None,
        staleness_days=_days_between(now, pushed) if pushed else None,
        has_description=bool(repo.description and repo.description.strip()),
    )


def language_breakdown(
    stats: LanguageStats,
    *,
    limit: int | None = None,
) -> list[LanguageShare]:
    """Break a language stats payload into sorted shares of the codebase."""
    total = stats.total_bytes
    if total <= 0:
        return []
    shares = [
        LanguageShare(language=name, bytes=bytes_, share=bytes_ / total)
        for name, bytes_ in stats.top_languages
    ]
    if limit is not None:
        shares = shares[:limit]
    return shares


def summarize_repositories(
    repos: Sequence[Repository],
    *,
    min_stars: int = 0,
    now: datetime | None = None,
) -> RepositorySummary:
    """Aggregate a repository list into summary metrics.

    Repositories below ``min_stars`` are excluded from the considered set.
    """
    now = now or datetime.now(UTC)
    considered = [repo for repo in repos if (repo.stargazers_count or 0) >= min_stars]
    stars = [repo.stargazers_count or 0 for repo in considered]
    languages = Counter(repo.language for repo in considered if repo.language)
    created = [(repo, _ensure_utc(repo.created_at)) for repo in considered if repo.created_at]
    pushed = [(repo, _ensure_utc(repo.pushed_at)) for repo in considered if repo.pushed_at]
    return RepositorySummary(
        considered_repositories=len(considered),
        total_stars=sum(stars),
        total_forks=sum(repo.forks_count or 0 for repo in considered),
        average_stars=sum(stars) / len(considered) if considered else 0.0,
        median_stars=median(stars) if stars else 0.0,
        top_language=languages.most_common(1)[0][0] if languages else None,
        language_counts=dict(languages),
        forked_count=sum(1 for repo in considered if repo.fork),
        archived_count=sum(1 for repo in considered if repo.archived),
        oldest_repository=min(created, key=lambda item: item[1])[0].full_name if created else None,
        newest_repository=max(created, key=lambda item: item[1])[0].full_name if created else None,
        stalest_repository=max(pushed, key=lambda item: item[1])[0].full_name if pushed else None,
    )


def commit_activity(
    commits: Sequence[Commit],
    *,
    author_login: str | None = None,
    author_email: str | None = None,
    now: datetime | None = None,
) -> CommitActivity:
    """Summarize commit volume and the activity window for one author.

    When neither ``author_login`` nor ``author_email`` is given, every commit
    counts as authored.
    """
    now = now or datetime.now(UTC)

    def is_author(commit: Commit) -> bool:
        if author_login is not None:
            return commit.author is not None and commit.author.login == author_login
        if author_email is not None:
            return (
                commit.commit is not None
                and commit.commit.author is not None
                and commit.commit.author.email == author_email
            )
        return True

    authored = [commit for commit in commits if is_author(commit)]
    dates = [
        _ensure_utc(commit.commit.author.date)
        for commit in authored
        if commit.commit is not None
        and commit.commit.author is not None
        and commit.commit.author.date is not None
    ]
    first = min(dates) if dates else None
    last = max(dates) if dates else None
    return CommitActivity(
        total_commits=len(commits),
        authored_commits=len(authored),
        first_commit_at=first,
        last_commit_at=last,
        unique_days=len({date.date() for date in dates}),
        recency_days=_days_between(now, last) if last else None,
    )


def issue_stats(
    issues: Sequence[Issue],
    *,
    author_login: str | None = None,
    now: datetime | None = None,
) -> IssueStats:
    """Summarize issue lifecycle, optionally restricted to one author."""
    now = now or datetime.now(UTC)
    if author_login is not None:
        issues = [
            issue for issue in issues if issue.user is not None and issue.user.login == author_login
        ]
    open_issues = [issue for issue in issues if issue.state == "open"]
    closed_issues = [
        issue
        for issue in issues
        if issue.state == "closed" and issue.created_at is not None and issue.closed_at is not None
    ]
    close_days = [
        _days_between(issue.closed_at, issue.created_at)
        for issue in closed_issues
        if issue.closed_at is not None and issue.created_at is not None
    ]
    oldest_open = min(
        (_ensure_utc(issue.created_at) for issue in open_issues if issue.created_at),
        default=None,
    )
    return IssueStats(
        total=len(issues),
        open=len(open_issues),
        closed=len(closed_issues),
        median_close_days=median(close_days) if close_days else None,
        oldest_open_days=_days_between(now, oldest_open) if oldest_open else None,
    )


def pull_request_stats(
    pulls: Sequence[PullRequest],
    *,
    author_login: str | None = None,
    now: datetime | None = None,
) -> PullRequestStats:
    """Summarize pull request lifecycle, optionally for one author."""
    now = now or datetime.now(UTC)
    if author_login is not None:
        pulls = [
            pull for pull in pulls if pull.user is not None and pull.user.login == author_login
        ]
    open_pulls = [pull for pull in pulls if pull.state == "open"]
    merged = [pull for pull in pulls if pull.merged]
    merge_days = [
        _days_between(pull.merged_at, pull.created_at)
        for pull in merged
        if pull.merged_at is not None and pull.created_at is not None
    ]
    oldest_open = min(
        (_ensure_utc(pull.created_at) for pull in open_pulls if pull.created_at),
        default=None,
    )
    return PullRequestStats(
        total=len(pulls),
        open=len(open_pulls),
        closed=sum(1 for pull in pulls if pull.state == "closed"),
        merged=len(merged),
        median_merge_days=median(merge_days) if merge_days else None,
        oldest_open_days=_days_between(now, oldest_open) if oldest_open else None,
    )


__all__ = [
    "CommitActivity",
    "IssueStats",
    "LanguageShare",
    "NormalizedRepository",
    "NormalizedUser",
    "PullRequestStats",
    "RepositorySummary",
    "ValidationRules",
    "commit_activity",
    "issue_stats",
    "language_breakdown",
    "normalize_repository",
    "normalize_user",
    "pull_request_stats",
    "summarize_repositories",
    "validate_sanity",
]
