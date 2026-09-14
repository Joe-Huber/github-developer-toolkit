"""Unit tests for profile summary assembly (issues #224, #225).

Verifies ``build_profile_identity``/``build_profile_top_stats`` and that the
report assembler exposes both blocks on ``ProfileAnalysis`` with honest
availability and provenance, across full, partial and empty snapshots.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ghdtk.analyzers.profile_summary import (
    build_profile_identity,
    build_profile_top_stats,
)
from ghdtk.models.derived.metric import MetricAvailability
from ghdtk.models.derived.provenance import SourceEntityKind
from ghdtk.models.raw import (
    CollectionRecord,
    CollectionStatus,
    ContributionCalendar,
    LanguageStats,
    ProfileSnapshot,
    Repository,
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
        "public_gists": 3,
        "created_at": "2015-01-10T00:00:00Z",
    }
    base.update(overrides)
    return User.model_validate(base)


def _repo(**overrides: Any) -> Repository:
    base: dict[str, Any] = {
        "name": "toolkit",
        "full_name": "octocat/toolkit",
        "description": "A developer toolkit",
        "stargazers_count": 250,
        "fork": False,
        "language": "Python",
        "html_url": "https://github.com/octocat/toolkit",
    }
    base.update(overrides)
    return Repository.model_validate(base)


def _snapshot(**kwargs: Any) -> ProfileSnapshot:
    base: dict[str, Any] = {
        "username": "octocat",
        "collected_at": NOW,
        "user": _user(),
        "repositories": [_repo()],
    }
    base.update(kwargs)
    return ProfileSnapshot.model_validate(base)


def _metric_value(stats: Any, metric_id: str) -> Any:
    for metric in stats.metrics:
        if metric.id == metric_id:
            return metric.value
    raise AssertionError(f"metric {metric_id!r} not found in {[m.id for m in stats.metrics]}")


def test_identity_forwarded_from_user_snapshot() -> None:
    identity = build_profile_identity(_user())
    assert identity is not None
    assert identity.username == "octocat"
    assert identity.name == "Mona Octocat"
    assert identity.bio is not None
    assert identity.avatar_url is None
    assert identity.followers == 1200
    assert identity.hireable is True
    assert identity.availability == MetricAvailability.AVAILABLE


def test_identity_none_when_user_snapshot_missing() -> None:
    assert build_profile_identity(None) is None


def test_top_stats_aggregates_owned_repositories_only() -> None:
    snapshot = _snapshot(
        repositories=[
            _repo(),
            _repo(name="resume", full_name="octocat/resume", stargazers_count=15),
        ],
        user=_user(public_repos=7),
    )
    stats = build_profile_top_stats("octocat", snapshot, now=NOW)
    assert _metric_value(stats, "top_stats.repositories") == 2
    assert _metric_value(stats, "top_stats.stars") == 265
    assert [repo.full_name for repo in stats.top_repositories] == [
        "octocat/toolkit",
        "octocat/resume",
    ]


def test_top_stats_excludes_two_forks() -> None:
    snapshot = _snapshot(
        repositories=[
            _repo(),
            _repo(name="fork", full_name="someone/fork", stargazers_count=999, fork=True),
        ]
    )
    stats = build_profile_top_stats("octocat", snapshot, now=NOW)
    assert _metric_value(stats, "top_stats.repositories") == 1
    assert _metric_value(stats, "top_stats.stars") == 250
    assert [repo.full_name for repo in stats.top_repositories] == ["octocat/toolkit"]


def test_top_stats_aggregates_languages_with_shares() -> None:
    snapshot = _snapshot(
        languages={
            "octocat/toolkit": LanguageStats.model_validate({"Python": 5000, "Go": 2500}),
            "octocat/resume": LanguageStats.model_validate({"HTML": 2500}),
        }
    )
    stats = build_profile_top_stats("octocat", snapshot, now=NOW)
    by_language = {lang.language: lang for lang in stats.top_languages}
    assert by_language["Python"].share == 0.5
    assert by_language["Go"].share == 0.25
    assert by_language["HTML"].share == 0.25


def test_top_stats_reports_partial_activity_metrics() -> None:
    stats = build_profile_top_stats("octocat", _snapshot(), now=NOW)
    for metric_id in ("top_stats.commits", "top_stats.pull_requests", "top_stats.issues"):
        metric = next(m for m in stats.metrics if m.id == metric_id)
        assert metric.availability == MetricAvailability.PARTIAL


def test_top_stats_contribution_total_from_calendar() -> None:
    snapshot = _snapshot(
        contribution_calendar=ContributionCalendar.model_validate({"totalContributions": 1240})
    )
    stats = build_profile_top_stats("octocat", snapshot, now=NOW)
    assert _metric_value(stats, "top_stats.contributions") == 1240


def test_top_stats_partial_when_snapshot_is_partial() -> None:
    snapshot = _snapshot(
        collections=[
            CollectionRecord(
                name="readme:octocat/toolkit",
                status=CollectionStatus.FAILED,
                reason="rate_limit",
            )
        ]
    )
    assert snapshot.is_partial
    stats = build_profile_top_stats("octocat", snapshot, now=NOW)
    assert stats.availability == MetricAvailability.PARTIAL


def test_top_stats_empty_snapshot_still_assembles() -> None:
    stats = build_profile_top_stats(
        "ghost", ProfileSnapshot(username="ghost", collected_at=NOW), now=NOW
    )
    assert stats.username == "ghost"
    assert _metric_value(stats, "top_stats.stars") == 0
    assert stats.top_repositories == []
    assert stats.top_languages == []
    assert stats.sources[0].entity == SourceEntityKind.PROFILE


def test_report_assembler_exposes_identity_and_top_stats() -> None:
    report = ReportAssembler().assemble(username="octocat", snapshot=_snapshot())
    assert report.profile.identity is not None
    assert report.profile.identity.name == "Mona Octocat"
    assert report.profile.top_stats is not None
    assert any(metric.id == "top_stats.stars" for metric in report.profile.top_stats.metrics)


def test_report_assembler_identity_none_without_user() -> None:
    snapshot = ProfileSnapshot(username="ghost", collected_at=NOW)
    report = ReportAssembler().assemble(username="ghost", snapshot=snapshot)
    assert report.profile.identity is None
    assert report.profile.top_stats is not None


def test_report_round_trips_with_profile_summary() -> None:
    report = ReportAssembler().assemble(username="octocat", snapshot=_snapshot())
    loaded = report.__class__.model_validate_json(report.model_dump_json())
    assert loaded == report
