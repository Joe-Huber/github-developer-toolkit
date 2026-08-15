"""Tests for star growth & trend analysis (issue #34)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ghdtk.analyzers.star_growth import StarGrowthAnalysis, StarGrowthStatus, assess_star_growth
from ghdtk.analyzers.thresholds import AnalysisThresholds
from ghdtk.models.derived import Finding, FindingSeverity
from ghdtk.models.raw import (
    CollectionRecord,
    CollectionStatus,
    ProfileSnapshot,
    Repository,
    Stargazer,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _repo(name: str, *, stars: int, fork: bool = False) -> Repository:
    return Repository(
        name=name,
        full_name=f"octocat/{name}",
        stargazers_count=stars,
        fork=fork,
    )


def _stargazer(login: str, *, days_ago: int) -> Stargazer:
    return Stargazer(login=login, starred_at=NOW - timedelta(days=days_ago))


def _snapshot(
    *,
    stars: int = 0,
    stargazers: list[Stargazer] | None = None,
    status: CollectionStatus = CollectionStatus.SUCCESS,
    record_name: str = "stargazers:octocat/A",
    reason: str | None = None,
) -> ProfileSnapshot:
    return ProfileSnapshot(
        username="octocat",
        collected_at=NOW,
        repositories=[_repo("A", stars=stars)],
        stargazers=stargazers,
        collections=[CollectionRecord(name=record_name, status=status, reason=reason)],
    )


def _metric(result: StarGrowthAnalysis, metric_id: str) -> int | float | bool | str | None:
    return next(metric.value for metric in result.metrics if metric.id == metric_id)


def _finding(result: StarGrowthAnalysis, finding_id: str) -> Finding:
    return next(finding for finding in result.findings if finding.id == finding_id)


def _rising_timeline() -> list[Stargazer]:
    return [
        _stargazer("u1", days_ago=2),
        _stargazer("u2", days_ago=5),
        _stargazer("u3", days_ago=10),
        _stargazer("u4", days_ago=20),
        _stargazer("u5", days_ago=100),
        _stargazer("u6", days_ago=200),
        _stargazer("u7", days_ago=300),
    ]


def test_rising_growth_with_complete_timeline() -> None:
    result = assess_star_growth(
        _snapshot(stars=7, stargazers=_rising_timeline()),
        now=NOW,
    )

    assert result.status is StarGrowthStatus.COMPLETE
    assert result.timeline_repo == "octocat/A"
    assert result.observed_stars == 7
    assert result.reported_stars == 7
    assert result.coverage == 1.0
    assert _metric(result, "star_growth.stars_30d") == 4
    assert _metric(result, "star_growth.stars_90d") == 4
    assert _metric(result, "star_growth.stars_365d") == 7
    assert _metric(result, "star_growth.trend") == "rising"

    finding = _finding(result, "star_growth.rising")
    assert finding.severity is FindingSeverity.INFO
    assert "1.3/month" in finding.message


def test_slowing_growth_detected() -> None:
    timeline = [
        _stargazer("u1", days_ago=95),
        _stargazer("u2", days_ago=400),
        _stargazer("u3", days_ago=700),
        _stargazer("u4", days_ago=1000),
        _stargazer("u5", days_ago=1300),
    ]
    result = assess_star_growth(_snapshot(stars=5, stargazers=timeline), now=NOW)

    assert result.status is StarGrowthStatus.COMPLETE
    assert _metric(result, "star_growth.trend") == "slowing"
    finding = _finding(result, "star_growth.slowing")
    assert finding.severity is FindingSeverity.LOW
    assert "0.0/month" in finding.message


def test_stable_growth_has_no_trend_finding() -> None:
    timeline = [_stargazer(f"u{i}", days_ago=30 * i + 5) for i in range(1, 9)]
    result = assess_star_growth(_snapshot(stars=8, stargazers=timeline), now=NOW)

    assert result.status is StarGrowthStatus.COMPLETE
    assert _metric(result, "star_growth.trend") == "stable"
    assert not any(
        finding.id in {"star_growth.rising", "star_growth.slowing"} for finding in result.findings
    )


def test_incomplete_timeline_reports_insufficient_data() -> None:
    timeline = _rising_timeline()
    result = assess_star_growth(_snapshot(stars=500, stargazers=timeline), now=NOW)

    assert result.status is StarGrowthStatus.INSUFFICIENT
    assert result.coverage == 7 / 500
    finding = _finding(result, "star_growth.insufficient_data")
    assert finding.severity is FindingSeverity.INFO
    assert "Only 7 of 500 reported stars" in finding.message
    assert _metric(result, "star_growth.trend") == "insufficient"
    assert not any(
        finding.id in {"star_growth.rising", "star_growth.slowing"} for finding in result.findings
    )


def test_sparse_timeline_reports_insufficient_data() -> None:
    timeline = [_stargazer("u1", days_ago=2), _stargazer("u2", days_ago=3)]
    result = assess_star_growth(_snapshot(stars=2, stargazers=timeline), now=NOW)

    assert result.status is StarGrowthStatus.INSUFFICIENT
    finding = _finding(result, "star_growth.insufficient_data")
    assert "spans 1 days" in finding.message


def test_failed_collection_reports_unavailable() -> None:
    result = assess_star_growth(
        _snapshot(
            stars=5,
            stargazers=None,
            status=CollectionStatus.FAILED,
            reason="GitHubAPIError",
        ),
        now=NOW,
    )

    assert result.status is StarGrowthStatus.INSUFFICIENT
    finding = _finding(result, "star_growth.insufficient_data")
    assert "not collected (GitHubAPIError)" in finding.message


def test_no_timeline_record() -> None:
    snapshot = ProfileSnapshot(
        username="octocat",
        collected_at=NOW,
        repositories=[_repo("A", stars=5)],
        collections=[],
    )
    result = assess_star_growth(snapshot, now=NOW)

    assert result.status is StarGrowthStatus.NO_TIMELINE
    assert result.timeline_repo is None
    assert result.observed_stars == 0
    assert result.coverage == 0.0
    finding = _finding(result, "star_growth.no_timeline")
    assert finding.severity is FindingSeverity.INFO


def test_zero_star_repo_reports_no_history() -> None:
    result = assess_star_growth(_snapshot(stars=0, stargazers=[]), now=NOW)

    assert result.status is StarGrowthStatus.INSUFFICIENT
    finding = _finding(result, "star_growth.insufficient_data")
    assert "reports no stars" in finding.message


def test_growth_window_is_config_driven() -> None:
    timeline = [
        _stargazer("u1", days_ago=5),
        _stargazer("u2", days_ago=10),
        _stargazer("u3", days_ago=100),
        _stargazer("u4", days_ago=200),
        _stargazer("u5", days_ago=300),
        _stargazer("u6", days_ago=400),
    ]
    default = assess_star_growth(_snapshot(stars=6, stargazers=timeline), now=NOW)
    assert default.status is StarGrowthStatus.COMPLETE
    assert _metric(default, "star_growth.trend") == "stable"

    narrow = assess_star_growth(
        _snapshot(stars=6, stargazers=timeline),
        now=NOW,
        thresholds=AnalysisThresholds(growth_window_days=30),
    )
    assert _metric(narrow, "star_growth.trend") == "rising"
    assert any(finding.id == "star_growth.rising" for finding in narrow.findings)


def test_slowing_threshold_is_config_driven() -> None:
    timeline = [
        _stargazer("u1", days_ago=10),
        _stargazer("u2", days_ago=100),
        _stargazer("u3", days_ago=130),
        _stargazer("u4", days_ago=160),
        _stargazer("u5", days_ago=190),
    ]
    default = assess_star_growth(_snapshot(stars=5, stargazers=timeline), now=NOW)
    assert _metric(default, "star_growth.trend") == "slowing"

    relaxed = assess_star_growth(
        _snapshot(stars=5, stargazers=timeline),
        now=NOW,
        thresholds=AnalysisThresholds(trend_slowing_ratio=0.3),
    )
    assert _metric(relaxed, "star_growth.trend") == "stable"
    assert not any(finding.id == "star_growth.slowing" for finding in relaxed.findings)
