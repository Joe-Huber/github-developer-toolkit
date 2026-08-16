"""Shared deterministic fixtures for report renderer tests (issue #56)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from ghdtk.models.derived import Report
from ghdtk.models.raw import (
    Commit,
    CommitDetail,
    ContributionCalendar,
    ContributionDay,
    ContributionWeek,
    Follower,
    Issue,
    ProfileReadme,
    ProfileReadmeStatus,
    ProfileSnapshot,
    PullRequest,
    PullRequestRef,
    Repository,
    Stargazer,
    User,
)
from ghdtk.report import ReportAssembler

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _user(**overrides: Any) -> User:
    base: dict[str, Any] = {
        "login": "octocat",
        "name": "Mona Octocat",
        "bio": "Building developer tools in the open.",
        "blog": "https://mona.dev",
        "company": "GitHub",
        "location": "San Francisco",
        "email": "mona@example.com",
        "hireable": True,
        "twitter_username": "mona",
        "followers": 1200,
        "following": 80,
        "public_repos": 6,
        "created_at": "2015-01-10T00:00:00Z",
    }
    base.update(overrides)
    return User.model_validate(base)


def _repo(**overrides: Any) -> Repository:
    base: dict[str, Any] = {
        "name": "toolkit",
        "full_name": "octocat/toolkit",
        "description": "A developer toolkit",
        "topics": ["python", "developer-tools"],
        "license": {"key": "mit", "name": "MIT License", "spdx_id": "MIT"},
        "homepage": "https://toolkit.example.com",
        "stargazers_count": 250,
        "fork": False,
        "archived": False,
        "created_at": "2016-03-01T00:00:00Z",
        "pushed_at": "2025-11-01T00:00:00Z",
    }
    base.update(overrides)
    return Repository.model_validate(base)


def _profile_readme() -> ProfileReadme:
    return ProfileReadme(
        username="octocat",
        status=ProfileReadmeStatus.PRESENT,
        content=(
            "# Hi there\n\n"
            "I build developer tools in the open.\n\n"
            "## Skills\n\n"
            "- Python\n- JavaScript\n\n"
            "## Contact\n\n"
            "[email me](mailto:mona@example.com)\n\n"
            "```python\nprint('hello')\n```"
        ),
        repository="octocat/octocat",
    )


def _commits() -> list[Commit]:
    return [
        Commit(
            sha="a" * 40,
            commit=CommitDetail(
                author={
                    "name": "Mona",
                    "email": "mona@example.com",
                    "date": "2025-10-01T10:00:00Z",
                },
                message="feat: add toolkit",
            ),
        ),
        Commit(
            sha="b" * 40,
            commit=CommitDetail(
                author={
                    "name": "Mona",
                    "email": "mona@example.com",
                    "date": "2025-11-01T11:00:00Z",
                },
                message="fix: improve docs",
            ),
        ),
    ]


def _stargazers() -> list[Stargazer]:
    return [
        Stargazer(login="follower-a", starred_at="2025-10-01T00:00:00Z"),
        Stargazer(login="follower-b", starred_at="2025-11-01T00:00:00Z"),
        Stargazer(login="follower-c", starred_at="2025-12-01T00:00:00Z"),
    ]


def _pull_requests() -> list[PullRequest]:
    return [
        PullRequest(
            number=1,
            title="Add developer toolkit",
            state="closed",
            merged=True,
            merged_at="2025-11-10T09:00:00Z",
            created_at="2025-11-05T09:00:00Z",
            closed_at="2025-11-10T09:00:00Z",
            comments=3,
            review_comments=2,
            repository_url="https://api.github.com/repos/octocat/toolkit",
            head=PullRequestRef(label="octocat:feat/toolkit", ref="feat/toolkit", sha="a" * 40),
        ),
        PullRequest(
            number=2,
            title="Open contribution",
            state="open",
            created_at="2025-12-20T09:00:00Z",
            comments=0,
            review_comments=0,
            repository_url="https://api.github.com/repos/octocat/second",
            head=PullRequestRef(label="octocat:feat/second", ref="feat/second", sha="b" * 40),
        ),
    ]


def _issues() -> list[Issue]:
    return [
        Issue(
            number=11,
            title="Bug in parser",
            state="closed",
            closed_at="2025-09-01T09:00:00Z",
            created_at="2025-08-20T09:00:00Z",
            comments=2,
            repository_url="https://api.github.com/repos/octocat/toolkit",
        ),
        Issue(
            number=12,
            title="Feature request",
            state="open",
            created_at="2025-12-01T09:00:00Z",
            comments=1,
            repository_url="https://api.github.com/repos/octocat/second",
        ),
    ]


def _calendar() -> ContributionCalendar:
    return ContributionCalendar(
        total_contributions=6,
        restricted_contributions_count=1,
        weeks=[
            ContributionWeek(
                first_day=date(2025, 12, 29),
                contribution_days=[
                    ContributionDay(date=date(2025, 12, 29), contribution_count=2),
                    ContributionDay(date=date(2025, 12, 30), contribution_count=3),
                    ContributionDay(date=date(2025, 12, 31), contribution_count=1),
                ],
            )
        ],
    )


def _rich_snapshot(**kwargs: Any) -> ProfileSnapshot:
    base: dict[str, Any] = {
        "username": "octocat",
        "collected_at": NOW,
        "user": _user(),
        "repositories": [
            _repo(),
            _repo(
                name="second",
                full_name="octocat/second",
                description="",
                stargazers_count=10,
                pushed_at="2024-01-01T00:00:00Z",
            ),
        ],
        "languages": {
            "octocat/toolkit": {"Python": 5000, "JavaScript": 3000},
            "octocat/second": {},
        },
        "commits": {"octocat/toolkit": _commits()},
        "search_pull_requests": _pull_requests(),
        "search_issues": _issues(),
        "followers": [
            Follower(login="follower-a"),
            Follower(login="follower-b"),
            Follower(login="follower-c"),
        ],
        "following": [Follower(login="hero"), Follower(login="mentor")],
        "stargazers": _stargazers(),
        "contribution_calendar": _calendar(),
        "collections": [
            {"name": "stargazers:octocat/toolkit", "status": "success"},
            {"name": "readme:octocat/toolkit", "status": "success"},
        ],
    }
    base.update(kwargs)
    return ProfileSnapshot.model_validate(base)


def _rich_report() -> Report:
    return ReportAssembler().assemble(
        username="octocat",
        snapshot=_rich_snapshot(),
        profile_readme=_profile_readme(),
    )


def _minimal_report() -> Report:
    snapshot = ProfileSnapshot(username="ghost", collected_at=NOW)
    return ReportAssembler().assemble(username="ghost", snapshot=snapshot)


def _userless_report() -> Report:
    snapshot = ProfileSnapshot.model_validate(
        {
            "username": "octocat",
            "collected_at": NOW,
            "repositories": [_repo().model_dump(mode="json")],
        }
    )
    return ReportAssembler().assemble(username="octocat", snapshot=snapshot)
