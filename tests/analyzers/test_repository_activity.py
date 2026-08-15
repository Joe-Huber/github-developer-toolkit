"""Tests for repository activity, age & consistency analysis (issue #30)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ghdtk.analyzers.repository_activity import (
    RepositoryActivity,
    RepositoryActivitySignals,
    assess_repository_activity,
)
from ghdtk.analyzers.thresholds import AnalysisThresholds
from ghdtk.models.derived import FindingSeverity
from ghdtk.models.raw import ProfileSnapshot, Repository

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _repo(
    name: str,
    *,
    created_days: int,
    pushed_days: int | None = None,
    updated_days: int | None = None,
    fork: bool = False,
    archived: bool = False,
) -> Repository:
    return Repository(
        name=name,
        full_name=f"octocat/{name}",
        created_at=NOW - timedelta(days=created_days),
        pushed_at=NOW - timedelta(days=pushed_days) if pushed_days is not None else None,
        updated_at=NOW - timedelta(days=updated_days) if updated_days is not None else None,
        fork=fork,
        archived=archived,
    )


def _snapshot(repos: list[Repository]) -> ProfileSnapshot:
    return ProfileSnapshot(username="octocat", collected_at=NOW, repositories=repos)


def _signal(result: RepositoryActivity, full_name: str) -> RepositoryActivitySignals:
    return next(signal for signal in result.signals if signal.full_name == full_name)


def _metric(result: RepositoryActivity, metric_id: str) -> int | float | str | None:
    return next(metric.value for metric in result.metrics if metric.id == metric_id)


def test_healthy_portfolio_counts_and_buckets() -> None:
    result = assess_repository_activity(
        _snapshot(
            [
                _repo("A", created_days=800, pushed_days=10),
                _repo("B", created_days=300, pushed_days=60),
                _repo("C", created_days=100, pushed_days=120),
                _repo("D", created_days=50, pushed_days=2, fork=True),
            ]
        ),
        now=NOW,
    )

    assert _metric(result, "portfolio.activity.repos.total") == 4
    assert _metric(result, "portfolio.activity.repos.active") == 2
    assert _metric(result, "portfolio.activity.repos.dormant") == 1
    assert _metric(result, "portfolio.activity.forked_repos") == 1
    assert _metric(result, "portfolio.activity.median_age_days") == 200
    assert _metric(result, "portfolio.activity.median_staleness_days") == 60
    assert _metric(result, "portfolio.activity.max_staleness_days") == 120
    assert _metric(result, "portfolio.activity.pushed_recently_30d") == 1
    assert _metric(result, "portfolio.activity.pushed_90d") == 2
    assert _metric(result, "portfolio.activity.pushed_365d") == 3
    assert _metric(result, "portfolio.activity.pushed_over_365d") == 0

    assert _signal(result, "octocat/A").active is True
    assert _signal(result, "octocat/C").active is False
    assert _signal(result, "octocat/C").stale is True
    assert _signal(result, "octocat/D").fork is True
    assert _signal(result, "octocat/D").active is False
    assert _signal(result, "octocat/D").stale is False

    stale = next(
        finding for finding in result.findings if finding.id == "repo.activity.stale.octocat/C"
    )
    assert stale.severity is FindingSeverity.LOW
    assert "120 days" in stale.message

    assert not any(
        finding.id == "portfolio.activity.no_recent_activity" for finding in result.findings
    )


def test_archived_repos_get_informational_finding_and_are_excluded() -> None:
    result = assess_repository_activity(
        _snapshot(
            [
                _repo("A", created_days=800, pushed_days=5, archived=True),
                _repo("B", created_days=300, pushed_days=3, fork=True),
                _repo("C", created_days=100, pushed_days=5),
            ]
        ),
        now=NOW,
    )

    archived = next(
        finding for finding in result.findings if finding.id == "repo.activity.archived.octocat/A"
    )
    assert archived.severity is FindingSeverity.INFO
    assert "archived" in archived.message

    assert _metric(result, "portfolio.activity.archived_repos") == 1
    assert _metric(result, "portfolio.activity.forked_repos") == 1
    assert _metric(result, "portfolio.activity.repos.active") == 1
    assert _metric(result, "portfolio.activity.repos.dormant") == 0
    assert _signal(result, "octocat/A").active is False
    assert _signal(result, "octocat/A").stale is False
    assert not any(
        finding.id == "portfolio.activity.no_recent_activity" for finding in result.findings
    )


def test_no_recent_activity_finding_when_nothing_was_pushed() -> None:
    result = assess_repository_activity(
        _snapshot(
            [
                _repo("A", created_days=800, pushed_days=100),
                _repo("B", created_days=300, pushed_days=200),
            ]
        ),
        now=NOW,
    )

    finding = next(
        finding
        for finding in result.findings
        if finding.id == "portfolio.activity.no_recent_activity"
    )
    assert finding.severity is FindingSeverity.MEDIUM
    assert "90-day" in finding.message


def test_longest_inactive_months_finding() -> None:
    result = assess_repository_activity(
        _snapshot([_repo("A", created_days=1500, pushed_days=400)]),
        now=NOW,
    )

    finding = next(
        finding
        for finding in result.findings
        if finding.id == "portfolio.activity.longest_inactive_months"
    )
    assert finding.severity is FindingSeverity.LOW
    assert "13 months" in finding.message


def test_staleness_threshold_is_config_driven() -> None:
    repo = _repo("A", created_days=800, pushed_days=60)

    default = assess_repository_activity(_snapshot([repo]), now=NOW)
    assert _metric(default, "portfolio.activity.repos.active") == 1
    assert not any(finding.id.startswith("repo.activity.stale.") for finding in default.findings)

    strict = assess_repository_activity(
        _snapshot([repo]),
        now=NOW,
        thresholds=AnalysisThresholds(staleness_days=30),
    )
    assert _metric(strict, "portfolio.activity.repos.active") == 0
    assert _metric(strict, "portfolio.activity.repos.dormant") == 1
    assert any(finding.id == "repo.activity.stale.octocat/A" for finding in strict.findings)


def test_empty_portfolio_has_no_findings() -> None:
    result = assess_repository_activity(_snapshot([]), now=NOW)

    assert result.signals == []
    assert result.findings == []
    assert _metric(result, "portfolio.activity.repos.total") == 0
    assert _metric(result, "portfolio.activity.repos.active") == 0
    assert _metric(result, "portfolio.activity.median_staleness_days") == 0


def test_missing_push_date_marks_signal_unknown() -> None:
    result = assess_repository_activity(
        _snapshot([_repo("A", created_days=800)]),
        now=NOW,
    )

    assert _signal(result, "octocat/A").unknown is True
    assert _signal(result, "octocat/A").active is False
    assert _signal(result, "octocat/A").stale is False
    assert _metric(result, "portfolio.activity.repos.active") == 0
    assert _metric(result, "portfolio.activity.repos.dormant") == 0
    assert not any(
        finding.id == "portfolio.activity.no_recent_activity" for finding in result.findings
    )


def test_updated_at_is_fallback_for_staleness() -> None:
    result = assess_repository_activity(
        _snapshot([_repo("A", created_days=100, pushed_days=None, updated_days=20)]),
        now=NOW,
    )

    assert _signal(result, "octocat/A").staleness_days == 20
    assert _signal(result, "octocat/A").active is True
    assert _signal(result, "octocat/A").unknown is False
