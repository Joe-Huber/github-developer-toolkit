"""Tests for commit history & activity analysis (issue #38)."""

from __future__ import annotations

from datetime import UTC, datetime

from ghdtk.analyzers.commits import CommitActivity, assess_commit_activity
from ghdtk.analyzers.thresholds import AnalysisThresholds
from ghdtk.models.derived import (
    DimensionId,
    FindingSeverity,
    MetricAvailability,
    MetricValue,
)
from ghdtk.models.raw import Commit, CommitDetail, GitUser, ProfileSnapshot

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _commit(iso: str) -> Commit:
    return Commit(
        sha=f"sha-{iso}",
        commit=CommitDetail(author=GitUser(date=datetime.fromisoformat(iso))),
    )


def _snapshot(commits: dict[str, list[Commit]]) -> ProfileSnapshot:
    return ProfileSnapshot(username="octocat", collected_at=NOW, commits=commits)


def _metric(result: CommitActivity, metric_id: str) -> MetricValue:
    return next(metric.value for metric in result.metrics if metric.id == metric_id)


def _availability(result: CommitActivity, metric_id: str) -> MetricAvailability:
    return next(metric.availability for metric in result.metrics if metric.id == metric_id)


def test_coverage_window_and_cadence() -> None:
    commits = {
        "octocat/A": [_commit("2024-01-05T10:00:00+00:00"), _commit("2024-01-06T10:00:00+00:00")],
        "octocat/B": [_commit("2024-01-07T10:00:00+00:00"), _commit("2024-02-01T10:00:00+00:00")],
    }
    result = assess_commit_activity(_snapshot(commits))

    assert result.total_commits == 4
    assert result.repos_collected == 2
    assert result.repos_with_commits == 2
    assert result.active_days == 4
    assert result.span_days == 28
    assert result.coverage_start is not None
    assert result.coverage_start.isoformat().startswith("2024-01-05")
    assert result.coverage_end is not None
    assert result.coverage_end.isoformat().startswith("2024-02-01")
    assert _metric(result, "commit_activity.total_commits") == 4
    assert _metric(result, "commit_activity.span_days") == 28
    assert _metric(result, "commit_activity.coverage_start") == "2024-01-05"
    assert _metric(result, "commit_activity.coverage_end") == "2024-02-01"
    assert _metric(result, "commit_activity.cadence_per_month") == 4.35

    finding = next(f for f in result.findings if f.id == "commit_activity.coverage_window")
    assert finding.severity is FindingSeverity.INFO
    assert finding.dimension is DimensionId.ACTIVITY
    assert "2024-01-05 to 2024-02-01" in finding.message
    assert "within the request budget" in finding.message


def test_long_gap_finding_and_median() -> None:
    commits = {
        "octocat/A": [
            _commit("2024-01-05T10:00:00+00:00"),
            _commit("2024-04-05T10:00:00+00:00"),
        ]
    }
    result = assess_commit_activity(_snapshot(commits))

    assert result.longest_gap_days == 91
    assert _metric(result, "commit_activity.longest_gap_days") == 91
    finding = next(f for f in result.findings if f.id == "commit_activity.long_gap")
    assert finding.severity is FindingSeverity.LOW
    assert "was 91 days" in finding.message
    assert _metric(result, "commit_activity.median_gap_days") == 91.0


def test_long_gap_threshold_is_config_driven() -> None:
    commits = {
        "octocat/A": [
            _commit("2024-01-05T10:00:00+00:00"),
            _commit("2024-01-06T10:00:00+00:00"),
            _commit("2024-01-07T10:00:00+00:00"),
            _commit("2024-02-01T10:00:00+00:00"),
        ]
    }
    default = assess_commit_activity(_snapshot(commits))
    assert default.longest_gap_days == 25
    assert not any(finding.id == "commit_activity.long_gap" for finding in default.findings)

    strict = assess_commit_activity(
        _snapshot(commits),
        thresholds=AnalysisThresholds(commit_gap_days=20),
    )
    assert any(finding.id == "commit_activity.long_gap" for finding in strict.findings)


def test_consistent_cadence_finding() -> None:
    commits = {
        "octocat/A": [
            _commit("2024-01-05T10:00:00+00:00"),
            _commit("2024-01-06T10:00:00+00:00"),
            _commit("2024-01-07T10:00:00+00:00"),
            _commit("2024-02-01T10:00:00+00:00"),
        ]
    }
    result = assess_commit_activity(_snapshot(commits))

    assert _metric(result, "commit_activity.cadence_per_month") == 4.35
    finding = next(f for f in result.findings if f.id == "commit_activity.consistent_cadence")
    assert finding.severity is FindingSeverity.INFO
    assert "4.3 commits per month" in finding.message


def test_no_commits() -> None:
    result = assess_commit_activity(_snapshot({}))

    assert result.total_commits == 0
    assert result.repos_collected == 0
    assert result.span_days is None
    assert _metric(result, "commit_activity.cadence_per_month") is None
    assert (
        _availability(result, "commit_activity.cadence_per_month") is MetricAvailability.UNAVAILABLE
    )
    finding = next(f for f in result.findings if f.id == "commit_activity.no_commits")
    assert finding.severity is FindingSeverity.INFO
    assert not any(finding.id == "commit_activity.coverage_window" for finding in result.findings)


def test_commits_without_dates_report_unavailable_window() -> None:
    commit = Commit(sha="sha-1", commit=CommitDetail(author=GitUser(name="octocat")))
    result = assess_commit_activity(_snapshot({"octocat/A": [commit]}))

    assert result.total_commits == 1
    assert result.span_days is None
    assert _metric(result, "commit_activity.coverage_start") is None
    assert _metric(result, "commit_activity.span_days") is None
    assert _availability(result, "commit_activity.coverage_start") is MetricAvailability.UNAVAILABLE
    assert _availability(result, "commit_activity.span_days") is MetricAvailability.UNAVAILABLE
    finding = next(f for f in result.findings if f.id == "commit_activity.no_dates")
    assert "none carried an author date" in finding.message


def test_per_repo_breakdown_and_top_repo() -> None:
    commits = {
        "octocat/A": [
            _commit("2024-01-05T10:00:00+00:00"),
            _commit("2024-01-06T10:00:00+00:00"),
        ],
        "octocat/B": [_commit("2024-01-07T10:00:00+00:00")],
    }
    result = assess_commit_activity(_snapshot(commits))

    assert result.per_repo_commits == {"octocat/A": 2, "octocat/B": 1}
    assert _metric(result, "commit_activity.repo.octocat/A") == 2
    assert _metric(result, "commit_activity.repo.octocat/B") == 1
    finding = next(f for f in result.findings if f.id == "commit_activity.top_repo")
    assert "2 of 3 collected commits" in finding.message


def test_weekday_and_hour_distribution() -> None:
    commits = {
        "octocat/A": [
            _commit("2024-01-08T09:15:00+00:00"),
            _commit("2024-01-10T22:30:00+00:00"),
        ]
    }
    result = assess_commit_activity(_snapshot(commits))

    assert result.weekday_counts["Mon"] == 1
    assert result.weekday_counts["Wed"] == 1
    assert result.weekday_counts["Sun"] == 0
    assert result.hour_bucket_counts["09-11"] == 1
    assert result.hour_bucket_counts["21-23"] == 1
    assert _metric(result, "commit_activity.weekday.Mon") == 1
    assert _metric(result, "commit_activity.hour.21-23") == 1
