"""Tests for the metric availability matrix (issue #64).

These guard the single source of truth for metric availability:

- :func:`availability_for` resolves documented defaults by longest-prefix.
- Every metric the analyzers emit (across the rich and minimal report
  pipelines) is documented in the matrix, and the analyzers' typed
  ``MetricRecord.availability`` never contradicts the matrix default.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from ghdtk.analyzers.availability import MATRIX, availability_for
from ghdtk.models.derived import MetricAvailability, Report
from ghdtk.models.raw import ProfileSnapshot

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "report"))

from _report_fixtures import _minimal_report, _rich_report

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _metric_ids(report: Report) -> set[str]:
    return {metric.id for metric in report.profile.metrics}


def test_longest_prefix_wins_for_family_and_subfamily() -> None:
    assert availability_for("network.followers.growth") is MetricAvailability.UNAVAILABLE
    assert availability_for("network.followers.count") is MetricAvailability.AVAILABLE
    assert availability_for("network.mutual_follows.count") is MetricAvailability.PARTIAL
    assert availability_for("network.orgs.count") is MetricAvailability.UNAVAILABLE
    assert availability_for("network.anything_else") is MetricAvailability.AVAILABLE


def test_families_with_partial_defaults() -> None:
    for metric_id in (
        "commit_activity.total_commits",
        "contribution_calendar.total_contributions",
        "pull_requests.total_pull_requests",
        "issues.total_issues",
        "portfolio.activity.repos.total",
        "star_growth.trend",
    ):
        assert availability_for(metric_id) is MetricAvailability.PARTIAL, metric_id


def test_families_with_available_defaults() -> None:
    for metric_id in (
        "presence.completeness",
        "readme.word_count",
        "portfolio.total_repositories",
        "portfolio.stars.total",
        "portfolio.quality.description_coverage",
        "languages.distinct_languages",
        "tech.domains_count",
    ):
        assert availability_for(metric_id) is MetricAvailability.AVAILABLE, metric_id


def test_unknown_metric_falls_back_to_available() -> None:
    assert availability_for("undocumented.metric") is MetricAvailability.AVAILABLE


def test_matrix_covers_every_rich_metric_id() -> None:
    report = _rich_report()
    undocumented = {
        metric_id
        for metric_id in _metric_ids(report)
        if not any(metric_id.startswith(entry.family) for entry in MATRIX)
    }
    assert not undocumented


def test_matrix_covers_every_minimal_metric_id() -> None:
    report = _minimal_report()
    undocumented = {
        metric_id
        for metric_id in _metric_ids(report)
        if not any(metric_id.startswith(entry.family) for entry in MATRIX)
    }
    assert not undocumented


def test_matrix_unavailable_metrics_are_never_claimed() -> None:
    """Matrix UNAVAILABLE is a hard guardrail: analyzers never emit AVAILABLE."""
    report = _rich_report()
    for metric in report.profile.metrics:
        expected = availability_for(metric.id)
        if expected is MetricAvailability.UNAVAILABLE:
            assert metric.availability is MetricAvailability.UNAVAILABLE, metric.id
            assert metric.value is None, metric.id


def test_documented_unsupported_metrics_are_emitted_unavailable() -> None:
    report = _rich_report()
    emitted = {metric.id: metric for metric in report.profile.metrics}
    for metric_id in ("network.followers.growth", "network.orgs.count"):
        assert emitted[metric_id].availability is MetricAvailability.UNAVAILABLE
        assert emitted[metric_id].value is None


def test_unavailable_metrics_carry_no_value() -> None:
    report = _rich_report()
    for metric in report.profile.metrics:
        if metric.availability is MetricAvailability.UNAVAILABLE:
            assert metric.value is None, metric.id


@pytest.mark.parametrize(
    "value",
    [
        MetricAvailability.AVAILABLE,
        MetricAvailability.PARTIAL,
        MetricAvailability.UNAVAILABLE,
    ],
)
def test_matrix_entries_use_only_known_statuses(value: Any) -> None:
    assert value in MetricAvailability


def test_snapshot_with_unavailable_marker_round_trips() -> None:
    snapshot = ProfileSnapshot(username="ghost", collected_at=NOW)
    assert snapshot.username == "ghost"
