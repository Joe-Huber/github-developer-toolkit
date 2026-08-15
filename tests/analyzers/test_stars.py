"""Tests for stars aggregation & distribution analysis (issue #33)."""

from __future__ import annotations

from datetime import UTC, datetime

from ghdtk.analyzers.stars import StarsAnalysis, assess_star_distribution
from ghdtk.analyzers.thresholds import AnalysisThresholds
from ghdtk.models.derived import FindingSeverity
from ghdtk.models.raw import ProfileSnapshot, Repository

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _repo(name: str, *, stars: int, fork: bool = False, archived: bool = False) -> Repository:
    return Repository(
        name=name,
        full_name=f"octocat/{name}",
        stargazers_count=stars,
        fork=fork,
        archived=archived,
    )


def _snapshot(repos: list[Repository]) -> ProfileSnapshot:
    return ProfileSnapshot(username="octocat", collected_at=NOW, repositories=repos)


def _metric(result: StarsAnalysis, metric_id: str) -> int | float | bool | str | None:
    return next(metric.value for metric in result.metrics if metric.id == metric_id)


def test_aggregation_and_ranking_flat_distribution() -> None:
    result = assess_star_distribution(
        _snapshot(
            [
                _repo("A", stars=30),
                _repo("B", stars=10),
                _repo("C", stars=0),
                _repo("D", stars=40),
            ]
        )
    )

    assert _metric(result, "portfolio.stars.total") == 80
    assert _metric(result, "portfolio.stars.average") == 20.0
    assert _metric(result, "portfolio.stars.median") == 20.0
    assert _metric(result, "portfolio.stars.max") == 40
    assert _metric(result, "portfolio.stars.repos_with_stars") == 3
    assert _metric(result, "portfolio.stars.repos_zero") == 1

    assert [entry.full_name for entry in result.ranking] == [
        "octocat/D",
        "octocat/A",
        "octocat/B",
        "octocat/C",
    ]
    assert result.ranking[0].rank == 1
    assert result.ranking[0].stars == 40
    assert result.ranking[-1].rank == 4

    assert not any(finding.id == "portfolio.stars.no_stars" for finding in result.findings)
    assert not any(finding.id == "portfolio.stars.fork_star_share" for finding in result.findings)


def test_skewed_distribution_percentiles_and_buckets() -> None:
    result = assess_star_distribution(
        _snapshot(
            [
                _repo("A", stars=5000),
                _repo("B", stars=120),
                _repo("C", stars=40),
                _repo("D", stars=5),
                _repo("E", stars=0),
            ]
        )
    )

    assert _metric(result, "portfolio.stars.p25") == 5.0
    assert _metric(result, "portfolio.stars.median") == 40.0
    assert _metric(result, "portfolio.stars.p75") == 120.0
    assert _metric(result, "portfolio.stars.p90") == 5000.0
    assert _metric(result, "portfolio.stars.p99") == 5000.0
    assert _metric(result, "portfolio.stars.bucket_0") == 1
    assert _metric(result, "portfolio.stars.bucket_1_9") == 1
    assert _metric(result, "portfolio.stars.bucket_10_99") == 1
    assert _metric(result, "portfolio.stars.bucket_100_999") == 1
    assert _metric(result, "portfolio.stars.bucket_1000_plus") == 1


def test_forked_stars_reported_separately() -> None:
    result = assess_star_distribution(
        _snapshot(
            [
                _repo("A", stars=30),
                _repo("B", stars=10, fork=True),
                _repo("C", stars=200, fork=True),
            ]
        )
    )

    assert _metric(result, "portfolio.stars.total") == 30
    assert _metric(result, "portfolio.stars.fork_stars") == 210
    assert [entry.full_name for entry in result.ranking] == ["octocat/A"]

    finding = next(
        finding for finding in result.findings if finding.id == "portfolio.stars.fork_star_share"
    )
    assert finding.severity is FindingSeverity.LOW
    assert "210 of 240" in finding.message
    assert "88%" in finding.message


def test_fork_star_share_threshold_is_config_driven() -> None:
    repos = [
        _repo("A", stars=30),
        _repo("B", stars=20, fork=True),
    ]
    result = assess_star_distribution(
        _snapshot(repos),
        thresholds=AnalysisThresholds(fork_ratio_threshold=0.9),
    )

    assert not any(finding.id == "portfolio.stars.fork_star_share" for finding in result.findings)


def test_no_stars_finding() -> None:
    result = assess_star_distribution(_snapshot([_repo("A", stars=0), _repo("B", stars=0)]))

    finding = next(
        finding for finding in result.findings if finding.id == "portfolio.stars.no_stars"
    )
    assert finding.severity is FindingSeverity.INFO
    assert "2 owned repositories" in finding.message
    assert _metric(result, "portfolio.stars.total") == 0


def test_archived_repositories_keep_their_stars() -> None:
    result = assess_star_distribution(
        _snapshot(
            [
                _repo("A", stars=100, archived=True),
                _repo("B", stars=20),
            ]
        )
    )

    assert _metric(result, "portfolio.stars.total") == 120
    assert [entry.full_name for entry in result.ranking] == ["octocat/A", "octocat/B"]
    assert result.ranking[0].archived is True


def test_empty_portfolio() -> None:
    result = assess_star_distribution(_snapshot([]))

    assert result.ranking == []
    assert _metric(result, "portfolio.stars.total") == 0
    assert _metric(result, "portfolio.stars.average") == 0.0
    assert _metric(result, "portfolio.stars.max") == 0
    assert result.findings == []
