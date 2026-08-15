"""Tests for portfolio composition & standout analysis (issue #31)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ghdtk.analyzers.portfolio import (
    PortfolioComposition,
    RepositoryCompositionSignals,
    assess_portfolio_composition,
)
from ghdtk.analyzers.thresholds import AnalysisThresholds
from ghdtk.models.derived import Finding, FindingSeverity
from ghdtk.models.raw import ProfileSnapshot, Repository

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _repo(
    name: str,
    *,
    stars: int,
    pushed_days: int | None = None,
    fork: bool = False,
    archived: bool = False,
) -> Repository:
    return Repository(
        name=name,
        full_name=f"octocat/{name}",
        stargazers_count=stars,
        pushed_at=NOW - timedelta(days=pushed_days) if pushed_days is not None else None,
        fork=fork,
        archived=archived,
    )


def _snapshot(repos: list[Repository]) -> ProfileSnapshot:
    return ProfileSnapshot(username="octocat", collected_at=NOW, repositories=repos)


def _signal(result: PortfolioComposition, full_name: str) -> RepositoryCompositionSignals:
    return next(signal for signal in result.signals if signal.full_name == full_name)


def _metric(result: PortfolioComposition, metric_id: str) -> int | float | bool | str | None:
    return next(metric.value for metric in result.metrics if metric.id == metric_id)


def _finding(result: PortfolioComposition, finding_id: str) -> Finding:
    return next(finding for finding in result.findings if finding.id == finding_id)


def test_standout_repositories_identified() -> None:
    result = assess_portfolio_composition(
        _snapshot(
            [
                _repo("A", stars=250, pushed_days=30),
                _repo("B", stars=10, pushed_days=10),
                _repo("C", stars=500, pushed_days=5, fork=True),
                _repo("D", stars=120, pushed_days=400),
                _repo("E", stars=40, pushed_days=60),
            ]
        ),
        now=NOW,
    )

    assert result.standouts == ["octocat/A"]
    assert _signal(result, "octocat/A").standout is True
    assert _signal(result, "octocat/B").standout is False
    assert _signal(result, "octocat/C").standout is False
    assert _signal(result, "octocat/D").standout is False

    standout = next(
        finding for finding in result.findings if finding.id == "repo.standout.octocat/A"
    )
    assert standout.severity is FindingSeverity.INFO
    assert "250" in standout.message

    assert _metric(result, "portfolio.standout.count") == 1
    assert _metric(result, "portfolio.standout.total_stars") == 250
    assert not any(
        finding.id == "portfolio.standout.none_identified" for finding in result.findings
    )


def test_no_standouts_when_none_qualify() -> None:
    result = assess_portfolio_composition(
        _snapshot(
            [
                _repo("A", stars=50, pushed_days=10),
                _repo("B", stars=30, pushed_days=20),
                _repo("C", stars=20, pushed_days=30),
            ]
        ),
        now=NOW,
    )

    assert result.standouts == []
    finding = _finding(result, "portfolio.standout.none_identified")
    assert finding.severity is FindingSeverity.INFO
    assert "100-star" in finding.message


def test_star_concentration_finding() -> None:
    result = assess_portfolio_composition(
        _snapshot(
            [
                _repo("A", stars=1600, pushed_days=30),
                _repo("B", stars=200, pushed_days=20),
                _repo("C", stars=200, pushed_days=10),
            ]
        ),
        now=NOW,
    )

    finding = _finding(result, "portfolio.composition.star_concentration")
    assert finding.severity is FindingSeverity.LOW
    assert "80%" in finding.message
    assert _metric(result, "portfolio.composition.top_repo_share") == 0.8
    assert _metric(result, "portfolio.composition.total_stars") == 2000


def test_no_concentration_when_stars_are_balanced() -> None:
    result = assess_portfolio_composition(
        _snapshot(
            [
                _repo("A", stars=400, pushed_days=30),
                _repo("B", stars=400, pushed_days=20),
                _repo("C", stars=200, pushed_days=10),
            ]
        ),
        now=NOW,
    )

    assert not any(
        finding.id == "portfolio.composition.star_concentration" for finding in result.findings
    )
    assert _metric(result, "portfolio.composition.top_repo_share") == 0.4


def test_fork_dominated_finding() -> None:
    result = assess_portfolio_composition(
        _snapshot(
            [
                _repo("A", stars=10, pushed_days=10, fork=True),
                _repo("B", stars=10, pushed_days=10, fork=True),
                _repo("C", stars=10, pushed_days=10),
            ]
        ),
        now=NOW,
    )

    finding = _finding(result, "portfolio.composition.fork_dominated")
    assert finding.severity is FindingSeverity.LOW
    assert "2 of 3" in finding.message
    assert _metric(result, "portfolio.composition.fork_ratio") == 0.67
    assert _metric(result, "portfolio.composition.own_count") == 1


def test_small_portfolio_suppresses_composition_findings() -> None:
    result = assess_portfolio_composition(
        _snapshot([_repo("A", stars=800, pushed_days=30)]),
        now=NOW,
    )

    small = _finding(result, "portfolio.composition.small_portfolio")
    assert small.severity is FindingSeverity.INFO
    assert "3-repository" in small.message
    assert not any(
        finding.id
        in {
            "portfolio.composition.star_concentration",
            "portfolio.standout.none_identified",
            "repo.standout.octocat/A",
        }
        for finding in result.findings
    )


def test_thresholds_are_config_driven() -> None:
    repos = [
        _repo("A", stars=120, pushed_days=30),
        _repo("B", stars=800, pushed_days=400),
        _repo("C", stars=30, pushed_days=10),
    ]
    relaxed = AnalysisThresholds(
        standout_star_threshold=50,
        standout_active_days=500,
        concentration_top_share=0.9,
    )
    result = assess_portfolio_composition(_snapshot(repos), now=NOW, thresholds=relaxed)

    assert result.standouts == ["octocat/A", "octocat/B"]
    assert not any(
        finding.id == "portfolio.composition.star_concentration" for finding in result.findings
    )
    assert not any(
        finding.id == "portfolio.standout.none_identified" for finding in result.findings
    )


def test_empty_portfolio() -> None:
    result = assess_portfolio_composition(_snapshot([]), now=NOW)

    assert result.signals == []
    assert result.standouts == []
    assert _metric(result, "portfolio.composition.repos.total") == 0
    assert _metric(result, "portfolio.composition.fork_ratio") == 0
    assert any(finding.id == "portfolio.composition.small_portfolio" for finding in result.findings)
