"""Unit tests for repository quality signals analysis (issue #29).

Exercises per-repository quality signals (description presence and
placeholder detection, README state, topics, license, website) and their
portfolio-level aggregation, using fixture repos covering quality extremes.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any

from ghdtk.analyzers import assess_repository_quality
from ghdtk.analyzers.thresholds import AnalysisThresholds
from ghdtk.models.derived import FindingSeverity
from ghdtk.models.raw import (
    CollectionRecord,
    CollectionStatus,
    ProfileSnapshot,
    Readme,
    Repository,
)

FixtureLoader = Any

NOW = datetime(2026, 1, 1, tzinfo=UTC)

RICH_README = (
    "# Polished\n\n"
    "A well maintained toolkit with many features.\n\n"
    "## Install\n\npip install polished\n"
)


def _repo(**overrides: Any) -> Repository:
    base: dict[str, Any] = {
        "name": "Polished",
        "full_name": "octocat/Polished",
        "description": "A well maintained toolkit",
        "topics": ["python", "toolkit"],
        "license": {"key": "mit", "name": "MIT License", "spdx_id": "MIT"},
        "homepage": "https://example.com",
        "stargazers_count": 200,
        "fork": False,
        "archived": False,
    }
    base.update(overrides)
    return Repository.model_validate(base)


def _readme(text: str) -> Readme:
    return Readme(
        type="file",
        encoding="base64",
        name="README.md",
        path="README.md",
        content=base64.b64encode(text.encode("utf-8")).decode("ascii"),
    )


def _snapshot(
    repos: list[Repository],
    *,
    readmes: dict[str, Readme] | None = None,
    readme_records: bool = True,
) -> ProfileSnapshot:
    collections: list[CollectionRecord] = []
    if readme_records:
        collections.extend(
            CollectionRecord(
                name=f"readme:{repo.full_name or ''}",
                status=CollectionStatus.SUCCESS,
            )
            for repo in repos
        )
    return ProfileSnapshot(
        username="octocat",
        collected_at=NOW,
        repositories=repos,
        readmes=readmes or {},
        collections=collections,
    )


def test_per_repo_signals_quality_extremes() -> None:
    repos = [
        _repo(
            name="Polished",
            full_name="octocat/Polished",
            description="A well maintained toolkit",
            topics=["python", "toolkit"],
            license={"key": "mit", "name": "MIT License"},
            homepage="https://example.com",
        ),
        _repo(
            name="Placeholder",
            full_name="octocat/Placeholder",
            description="your project",
            topics=[],
            license=None,
            homepage=None,
        ),
        _repo(
            name="Bare",
            full_name="octocat/Bare",
            description=None,
            topics=[],
            license=None,
            homepage=None,
        ),
    ]
    result = assess_repository_quality(
        _snapshot(
            repos,
            readmes={"octocat/Polished": _readme(RICH_README)},
        )
    )

    by_name = {signal.full_name: signal for signal in result.signals}
    polished = by_name["octocat/Polished"]
    assert polished.has_description is True
    assert polished.description_placeholder is False
    assert polished.readme.value == "present"
    assert polished.readme_chars == len(RICH_README)
    assert polished.topics_count == 2
    assert polished.has_license is True
    assert polished.license_name == "MIT License"
    assert polished.has_homepage is True

    placeholder = by_name["octocat/Placeholder"]
    assert placeholder.description_placeholder is True
    assert placeholder.readme.value == "absent"

    bare = by_name["octocat/Bare"]
    assert bare.has_description is False
    assert bare.readme.value == "absent"


def test_per_repo_findings() -> None:
    repos = [
        _repo(name="Placeholder", full_name="octocat/Placeholder", description="your project"),
        _repo(name="Bare", full_name="octocat/Bare", description=None),
    ]
    result = assess_repository_quality(_snapshot(repos))

    finding_ids = {finding.id for finding in result.findings}
    assert "repo.quality.no_description.octocat/Bare" in finding_ids
    assert "repo.quality.placeholder_description.octocat/Placeholder" in finding_ids
    assert "repo.quality.no_readme.octocat/Placeholder" in finding_ids
    assert "repo.quality.no_readme.octocat/Bare" in finding_ids

    placeholder = next(
        finding
        for finding in result.findings
        if finding.id == "repo.quality.placeholder_description.octocat/Placeholder"
    )
    assert placeholder.severity is FindingSeverity.MEDIUM
    assert placeholder.evidence[0].identifier == "octocat/Placeholder"
    assert placeholder.evidence[0].field == "description"


def test_readme_unknown_when_not_collected() -> None:
    repos = [_repo(name="Skipped", full_name="octocat/Skipped", description="ok")]
    result = assess_repository_quality(_snapshot(repos, readme_records=False))

    signal = result.signals[0]
    assert signal.readme.value == "unknown"
    assert not any(
        finding.id == "repo.quality.no_readme.octocat/Skipped" for finding in result.findings
    )


def test_portfolio_aggregation_metrics() -> None:
    repos = [
        _repo(name="A", full_name="octocat/A", description="one"),
        _repo(name="B", full_name="octocat/B", description=None),
        _repo(name="C", full_name="octocat/C", description="three"),
    ]
    result = assess_repository_quality(_snapshot(repos))

    metric_by_id = {metric.id: metric for metric in result.metrics}
    assert metric_by_id["portfolio.repositories.count"].value == 3
    assert metric_by_id["portfolio.quality.description_coverage"].value == 2 / 3
    assert metric_by_id["portfolio.quality.readme_coverage"].value == 0.0
    assert metric_by_id["portfolio.quality.license_coverage"].value == 1.0
    assert metric_by_id["portfolio.quality.homepage_coverage"].value == 1.0
    assert metric_by_id["portfolio.quality.topics.average"].value == 2.0
    assert metric_by_id["portfolio.quality.repos_no_description"].value == 1
    assert metric_by_id["portfolio.quality.repos_no_readme"].value == 3


def test_low_readme_coverage_finding() -> None:
    repos = [
        _repo(name="A", full_name="octocat/A", description="one"),
        _repo(name="B", full_name="octocat/B", description="two"),
        _repo(name="C", full_name="octocat/C", description=None),
    ]
    result = assess_repository_quality(
        _snapshot(repos, readmes={"octocat/A": _readme(RICH_README)})
    )

    finding = next(
        finding
        for finding in result.findings
        if finding.id == "portfolio.quality.low_readme_coverage"
    )
    assert finding.severity is FindingSeverity.MEDIUM
    assert "33%" in finding.message
    assert not any(
        finding.id == "portfolio.quality.low_description_coverage" for finding in result.findings
    )

    finding = next(
        finding
        for finding in result.findings
        if finding.id == "portfolio.quality.low_readme_coverage"
    )
    assert finding.severity is FindingSeverity.MEDIUM
    assert "33%" in finding.message
    assert not any(
        finding.id == "portfolio.quality.low_description_coverage" for finding in result.findings
    )


def test_coverage_threshold_is_config_driven() -> None:
    repos = [
        _repo(name="A", full_name="octocat/A", description="one"),
        _repo(name="B", full_name="octocat/B", description=None),
        _repo(name="C", full_name="octocat/C", description=None),
    ]
    thresholds = AnalysisThresholds(quality_coverage_threshold=0.9)
    result = assess_repository_quality(_snapshot(repos), thresholds=thresholds)

    finding = next(
        finding
        for finding in result.findings
        if finding.id == "portfolio.quality.low_description_coverage"
    )
    assert finding.severity is FindingSeverity.MEDIUM
    assert "33%" in finding.message
    assert "90%" in finding.message


def test_thin_readme_finding() -> None:
    repos = [_repo(name="Thin", full_name="octocat/Thin", description="ok")]
    result = assess_repository_quality(_snapshot(repos, readmes={"octocat/Thin": _readme("hi")}))

    finding = next(
        finding
        for finding in result.findings
        if finding.id == "repo.quality.thin_readme.octocat/Thin"
    )
    assert finding.severity is FindingSeverity.LOW
    assert finding.evidence[0].field == "readme"


def test_empty_portfolio() -> None:
    result = assess_repository_quality(_snapshot([]))

    assert result.signals == []
    assert result.findings == []
    metric_by_id = {metric.id: metric for metric in result.metrics}
    assert metric_by_id["portfolio.repositories.count"].value == 0
