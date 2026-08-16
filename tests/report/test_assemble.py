"""Unit tests for report data assembly (issue #55).

Verifies that the assembler runs the full pipeline over a raw snapshot and
composes every section — analyses, metrics, findings, scores, overall,
recommendations and synthesis — into a consistent, deterministic,
JSON-round-trippable report, across fixture profiles.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ghdtk.models.raw import (
    CollectionRecord,
    CollectionStatus,
    ProfileReadme,
    ProfileReadmeStatus,
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
        "pushed_at": "2025-11-01T00:00:00Z",
    }
    base.update(overrides)
    return Repository.model_validate(base)


def _snapshot(
    *,
    user: User | None = None,
    repos: list[Repository] | None = None,
    include_user: bool = True,
    **kwargs: Any,
) -> ProfileSnapshot:
    if not include_user:
        user = None
    elif user is None:
        user = _user()
    base: dict[str, Any] = {
        "username": "octocat",
        "collected_at": NOW,
        "user": user,
        "repositories": repos or [_repo()],
    }
    base.update(kwargs)
    return ProfileSnapshot.model_validate(base)


def _profile_readme() -> ProfileReadme:
    return ProfileReadme(
        username="octocat",
        status=ProfileReadmeStatus.PRESENT,
        content="# Hi there\n\nI build developer tools.",
        repository="octocat/octocat",
    )


def test_assembles_all_sections_for_a_rich_profile() -> None:
    report = ReportAssembler().assemble(
        username="octocat",
        snapshot=_snapshot(),
        profile_readme=_profile_readme(),
    )
    profile = report.profile
    assert profile.username == "octocat"
    assert profile.analyzed_at == NOW

    assert profile.analyses is not None
    assert profile.analyses.presence is not None
    assert profile.analyses.readme is not None
    assert profile.analyses.repository_quality is not None
    assert profile.analyses.repository_activity is not None
    assert profile.analyses.portfolio is not None
    assert profile.analyses.stars is not None
    assert profile.analyses.star_growth is not None
    assert profile.analyses.network is not None
    assert profile.analyses.commits is not None
    assert profile.analyses.contribution_calendar is not None
    assert profile.analyses.pull_requests is not None
    assert profile.analyses.issues is not None
    assert profile.analyses.languages is not None
    assert profile.analyses.technology is not None

    assert profile.metrics
    assert profile.findings
    assert profile.scores
    assert profile.overall is not None
    assert profile.recommendations
    assert profile.synthesis is not None


def test_metrics_and_findings_flattened_in_canonical_analyzer_order() -> None:
    report = ReportAssembler().assemble(
        username="octocat", snapshot=_snapshot(), profile_readme=_profile_readme()
    )
    analyses = report.profile.analyses
    assert analyses is not None
    expected_metric_ids = [
        metric.id
        for analysis in (analyses.presence, analyses.readme)
        if analysis is not None
        for metric in analysis.metrics
    ]
    flat = [metric.id for metric in report.profile.metrics]
    assert flat[: len(expected_metric_ids)] == expected_metric_ids


def test_report_round_trips_to_json_losslessly() -> None:
    report = ReportAssembler().assemble(
        username="octocat", snapshot=_snapshot(), profile_readme=_profile_readme()
    )
    loaded = report.__class__.model_validate_json(report.model_dump_json())
    assert loaded == report


def test_assembly_is_deterministic() -> None:
    assembler = ReportAssembler()
    first = assembler.assemble(username="octocat", snapshot=_snapshot())
    second = assembler.assemble(username="octocat", snapshot=_snapshot())
    assert first == second


def test_metrics_ordering_is_consistent_across_runs() -> None:
    assembler = ReportAssembler()
    first = assembler.assemble(username="octocat", snapshot=_snapshot())
    second = assembler.assemble(username="octocat", snapshot=_snapshot())
    assert [m.id for m in first.profile.metrics] == [m.id for m in second.profile.metrics]


def test_missing_user_and_readme_are_reported_honestly() -> None:
    report = ReportAssembler().assemble(
        username="octocat",
        snapshot=_snapshot(include_user=False),
    )
    analyses = report.profile.analyses
    assert analyses is not None
    assert analyses.presence is None
    assert analyses.readme is None
    assert not any(metric.id.startswith("presence.") for metric in report.profile.metrics)
    assert not any(metric.id.startswith("readme.") for metric in report.profile.metrics)
    assert all(score.dimension.value != "presence" for score in report.profile.scores)


def test_minimal_profile_still_assembles() -> None:
    report = ReportAssembler().assemble(
        username="ghost",
        snapshot=ProfileSnapshot(username="ghost", collected_at=NOW),
    )
    assert report.profile.username == "ghost"
    assert report.profile.analyses is not None
    assert report.profile.synthesis is not None


def test_snapshot_collection_time_defaults_now() -> None:
    report = ReportAssembler().assemble(username="octocat", snapshot=_snapshot())
    assert report.profile.analyzed_at == NOW
    assert report.generated_at == NOW


def test_partial_snapshot_disclosures_are_preserved() -> None:
    snapshot = _snapshot(
        repositories=[
            _repo(),
            _repo(name="second", full_name="octocat/second", stargazers_count=10),
        ],
        collections=[
            CollectionRecord(
                name="readme:octocat/toolkit",
                status=CollectionStatus.SUCCESS,
            ),
            CollectionRecord(
                name="readme:octocat/second",
                status=CollectionStatus.FAILED,
                reason="rate_limit",
            ),
        ],
    )
    report = ReportAssembler().assemble(username="octocat", snapshot=snapshot)
    assert snapshot.is_partial
    assert report.profile.analyses is not None
    assert report.profile.analyses.repository_quality is not None


def test_assembler_accepts_custom_now() -> None:
    later = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    report = ReportAssembler().assemble(username="octocat", snapshot=_snapshot(), now=later)
    assert report.profile.analyzed_at == later


def test_profile_readme_content_surfaces_in_readme_analysis() -> None:
    report = ReportAssembler().assemble(
        username="octocat",
        snapshot=_snapshot(),
        profile_readme=_profile_readme(),
    )
    readme = report.profile.analyses
    assert readme is not None
    assert readme.readme is not None
    assert readme.readme.metrics[0].id == "readme.present"
