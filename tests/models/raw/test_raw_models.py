"""Unit tests for raw GitHub data models (see issue #14).

Verifies that payload fixtures deserialize into raw models with field
fidelity, that missing/extra fields never raise, and that raw models behave as
immutable source-of-truth snapshots.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from ghdtk.models.raw import (
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


def test_user_fidelity(load_raw_fixture: Any) -> None:
    user = User.model_validate(load_raw_fixture("user"))
    assert user.login == "octocat"
    assert user.id == 1
    assert user.name == "Monalisa Octocat"
    assert user.company == "GitHub"
    assert user.location == "San Francisco"
    assert user.public_repos == 2
    assert user.followers == 20
    assert user.created_at == datetime(2008, 1, 14, 4, 33, 35, tzinfo=UTC)


def test_user_requires_login() -> None:
    with pytest.raises(ValidationError):
        User.model_validate({"id": 1})


def test_user_optional_fields_default_to_none() -> None:
    user = User(login="minimal")
    assert user.id is None
    assert user.bio is None
    assert user.site_admin is None
    assert user.created_at is None


def test_user_extra_fields_ignored() -> None:
    user = User.model_validate({"login": "x", "unexpected_field": 123})
    assert user.login == "x"
    assert "unexpected_field" not in user.model_fields_set


def test_user_immutable() -> None:
    user = User(login="x")
    with pytest.raises(ValidationError):
        user.login = "y"  # type: ignore[misc]


def test_repository_fidelity(load_raw_fixture: Any) -> None:
    repo = Repository.model_validate(load_raw_fixture("repository"))
    assert repo.full_name == "octocat/Hello-World"
    assert repo.stargazers_count == 80
    assert repo.language == "Python"
    assert repo.default_branch == "main"
    assert repo.topics == ["octocat", "atom", "electron", "api"]
    assert repo.owner is not None and repo.owner.login == "octocat"
    assert repo.license is not None and repo.license.key == "mit"
    assert repo.created_at == datetime(2011, 1, 26, 19, 1, 12, tzinfo=UTC)


def test_repository_empty_payload_ok() -> None:
    repo = Repository.model_validate({})
    assert repo.full_name is None
    assert repo.private is None
    assert repo.owner is None


def test_repository_immutable(load_raw_fixture: Any) -> None:
    repo = Repository.model_validate(load_raw_fixture("repository"))
    with pytest.raises(ValidationError):
        repo.full_name = "changed"  # type: ignore[misc]


def test_readme_decodes_base64(load_raw_fixture: Any) -> None:
    readme = Readme.model_validate(load_raw_fixture("readme"))
    assert readme.name == "README.md"
    assert readme.encoding == "base64"
    assert readme.decoded_content is not None
    assert "# Acme Toolkit" in readme.decoded_content


def test_readme_empty_payload_ok() -> None:
    readme = Readme.model_validate({})
    assert readme.content is None
    assert readme.decoded_content is None


def test_commit_fidelity(load_raw_fixture: Any) -> None:
    commit = Commit.model_validate(load_raw_fixture("commit"))
    assert commit.sha == "c441029cf673f84c8b7db4892590f29e1ed8c5e4"
    assert commit.commit is not None
    assert commit.commit.message == "First commit!"
    assert commit.commit.author is not None
    assert commit.commit.author.name == "Monalisa Octocat"
    assert commit.commit.verification is not None
    assert commit.commit.verification.verified is False
    assert commit.author is not None and commit.author.login == "octocat"
    assert commit.parents is not None
    assert commit.parents[0].sha is not None
    assert commit.parents[0].sha.startswith("553c20")


def test_pull_request_fidelity(load_raw_fixture: Any) -> None:
    pr = PullRequest.model_validate(load_raw_fixture("pull_request"))
    assert pr.number == 1347
    assert pr.state == "open"
    assert pr.title == "new-feature"
    assert pr.merged is False
    assert pr.additions == 100
    assert pr.deletions == 3
    assert pr.head is not None and pr.head.ref == "new-feature"
    assert pr.head is not None and pr.head.repo is not None
    assert pr.head.repo.full_name == "octocat/Hello-World"
    assert pr.labels is not None and pr.labels[0].name == "bug"
    assert pr.merged_at is None


def test_issue_fidelity(load_raw_fixture: Any) -> None:
    issue = Issue.model_validate(load_raw_fixture("issue"))
    assert issue.number == 1347
    assert issue.state == "open"
    assert issue.title == "Found a bug"
    assert issue.labels is not None and issue.labels[0].name == "bug"
    assert issue.milestone is not None and issue.milestone.title == "v1.0"
    assert issue.pull_request is None


def test_language_stats(load_raw_fixture: Any) -> None:
    stats = LanguageStats.model_validate(load_raw_fixture("language_stats"))
    assert stats.root["Python"] == 38739
    assert stats.total_bytes == 82_249
    assert stats.top_languages[0] == ("HTML", 41126)


def test_language_stats_immutable(load_raw_fixture: Any) -> None:
    stats = LanguageStats.model_validate(load_raw_fixture("language_stats"))
    with pytest.raises(ValidationError):
        stats.root = {}  # type: ignore[misc]


def test_stargazer_fidelity(load_raw_fixture: Any) -> None:
    stargazer = Stargazer.model_validate(load_raw_fixture("stargazer"))
    assert stargazer.login == "octocat"
    assert stargazer.id == 1
    assert stargazer.starred_at is None


def test_follower_fidelity(load_raw_fixture: Any) -> None:
    follower = Follower.model_validate(load_raw_fixture("follower"))
    assert follower.login == "torvalds"
    assert follower.id == 1024025
    assert follower.followed_at is None


def test_contribution_calendar_graphql_payload(load_raw_fixture: Any) -> None:
    calendar = ContributionCalendar.model_validate(load_raw_fixture("contribution_calendar"))
    assert calendar.total_contributions == 100
    assert calendar.weeks is not None and len(calendar.weeks) == 2
    assert calendar.weeks[0].contribution_days is not None
    first_day = calendar.weeks[0].contribution_days[0]
    assert first_day.date == date(2024, 1, 1)
    assert first_day.contribution_count == 0
    assert first_day.color == "#ebedf0"
    assert calendar.weeks[0].first_day == date(2024, 1, 1)


def test_contribution_calendar_snake_case_accepted() -> None:
    calendar = ContributionCalendar.model_validate({"total_contributions": 5, "weeks": None})
    assert calendar.total_contributions == 5
    assert calendar.weeks is None
