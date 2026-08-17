"""Tests for language distribution & primary languages analysis (issue #44)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ghdtk.analyzers.languages import (
    LanguageDistributionAnalysis,
    assess_language_distribution,
)
from ghdtk.analyzers.thresholds import AnalysisThresholds
from ghdtk.models.derived import (
    DimensionId,
    FindingSeverity,
    MetricAvailability,
    MetricValue,
)
from ghdtk.models.raw import LanguageStats, ProfileSnapshot, Repository

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _language_stats(**languages: int) -> LanguageStats:
    return LanguageStats(languages)


def _repo(
    name: str,
    *,
    language: str | None = None,
    topics: list[str] | None = None,
) -> Repository:
    return Repository(full_name=f"octocat/{name}", language=language, topics=topics)


def _snapshot(
    repos: list[Repository],
    *,
    languages: dict[str, LanguageStats] | None = None,
) -> ProfileSnapshot:
    return ProfileSnapshot(
        username="octocat",
        collected_at=NOW,
        repositories=repos,
        languages=languages or {},
    )


def _metric(result: LanguageDistributionAnalysis, metric_id: str) -> MetricValue:
    return next(metric.value for metric in result.metrics if metric.id == metric_id)


def _availability(result: LanguageDistributionAnalysis, metric_id: str) -> MetricAvailability:
    return next(metric.availability for metric in result.metrics if metric.id == metric_id)


def _repo_row(result: LanguageDistributionAnalysis, full_name: str) -> Any:
    return next(row for row in result.repositories if row.full_name == full_name)


def test_language_distribution_from_fixture(load_raw_fixture: Any) -> None:
    snapshot = ProfileSnapshot.model_validate(load_raw_fixture("languages_mix"))
    result = assess_language_distribution(snapshot)

    assert result.total_bytes == 176_072
    assert result.distinct_languages == 7
    assert result.dominant_language == "Python"
    assert result.dominant_share == 0.5
    assert result.repos_with_stats == 4
    assert result.declared_only_count == 1
    assert result.unknown_count == 1
    assert result.empty_count == 1

    assert result.distribution[0].language == "Python"
    assert result.distribution[0].bytes == 88_739
    assert result.distribution[0].share == 0.5
    assert result.distribution[1].language == "HTML"
    assert result.distribution[1].share == 0.23

    assert _repo_row(result, "octocat/Hello-World").primary == "HTML"
    assert _repo_row(result, "octocat/web-front").primary == "JavaScript"
    assert _repo_row(result, "octocat/data-tools").primary == "Python"
    assert _repo_row(result, "octocat/empty-repo").primary is None
    assert _repo_row(result, "octocat/declared-only").primary == "Go"
    assert _repo_row(result, "octocat/declared-only").has_byte_stats is False
    assert _repo_row(result, "octocat/no-data").primary is None

    assert _metric(result, "languages.repos.total") == 6
    assert _metric(result, "languages.repos.with_byte_stats") == 4
    assert _metric(result, "languages.repos.declared_only") == 1
    assert _metric(result, "languages.repos.unknown") == 1
    assert _metric(result, "languages.repos.empty") == 1
    assert _metric(result, "languages.total_bytes") == 176_072
    assert _metric(result, "languages.distinct_languages") == 7
    assert _metric(result, "languages.dominant_language") == "Python"
    assert _metric(result, "languages.dominant_share") == 0.5
    assert _metric(result, "languages.share.Python") == 0.5
    assert _metric(result, "languages.bytes.Python") == 88_739
    assert _metric(result, "languages.primary.octocat/Hello-World") == "HTML"
    assert _metric(result, "languages.repo_bytes.octocat/web-front") == 35_000

    coverage = next(f for f in result.findings if f.id == "languages.coverage_gap")
    assert coverage.dimension is DimensionId.CODE_QUALITY
    assert "byte statistics" in coverage.message

    empty = next(f for f in result.findings if f.id == "languages.empty_repositories")
    assert "no detectable code" in empty.title

    polyglot = next(f for f in result.findings if f.id == "languages.polyglot")
    assert polyglot.severity is FindingSeverity.INFO

    assert not any(f.id == "languages.concentrated" for f in result.findings)
    assert not any(f.id == "languages.no_data" for f in result.findings)
    assert not any(f.id == "languages.no_repositories" for f in result.findings)


def test_concentration_threshold_is_config_driven() -> None:
    repos = [
        _repo("ml", language="Python"),
        _repo("etl", language="Python"),
    ]
    languages = {
        "octocat/ml": _language_stats(Python=90_000, HTML=20_000),
        "octocat/etl": _language_stats(Python=10_000),
    }
    default = assess_language_distribution(_snapshot(repos, languages=languages))
    assert default.dominant_language == "Python"
    assert default.dominant_share == 0.83
    finding = next(f for f in default.findings if f.id == "languages.concentrated")
    assert finding.severity is FindingSeverity.LOW
    assert any(ref.identifier == "octocat/ml" for ref in finding.evidence)

    strict = assess_language_distribution(
        _snapshot(repos, languages=languages),
        thresholds=AnalysisThresholds(language_concentration_threshold=0.95),
    )
    assert not any(f.id == "languages.concentrated" for f in strict.findings)


def test_polyglot_threshold_is_config_driven() -> None:
    repos = [_repo("a"), _repo("b"), _repo("c"), _repo("d"), _repo("e")]
    languages = {
        "octocat/a": _language_stats(Python=100),
        "octocat/b": _language_stats(Go=100),
        "octocat/c": _language_stats(Rust=100),
        "octocat/d": _language_stats(TypeScript=100),
        "octocat/e": _language_stats(Kotlin=100),
    }
    default = assess_language_distribution(_snapshot(repos, languages=languages))
    assert default.distinct_languages == 5
    assert any(f.id == "languages.polyglot" for f in default.findings)

    strict = assess_language_distribution(
        _snapshot(repos, languages=languages),
        thresholds=AnalysisThresholds(language_distinct_threshold=6),
    )
    assert not any(f.id == "languages.polyglot" for f in strict.findings)


def test_declared_only_and_unknown_repos() -> None:
    repos = [
        _repo("declared", language="Go"),
        _repo("no-data"),
    ]
    result = assess_language_distribution(_snapshot(repos))

    assert result.repos_with_stats == 0
    assert result.declared_only_count == 1
    assert result.unknown_count == 1
    assert result.total_bytes == 0
    assert result.dominant_language is None
    assert result.distribution == []
    assert _metric(result, "languages.primary.octocat/declared") == "Go"
    assert _metric(result, "languages.repo_bytes.octocat/declared") is None
    assert (
        _availability(result, "languages.repo_bytes.octocat/declared")
        is MetricAvailability.UNAVAILABLE
    )

    coverage = next(f for f in result.findings if f.id == "languages.coverage_gap")
    assert "1 repository(ies) only carry a declared primary language" in coverage.message
    assert not any(f.id == "languages.no_data" for f in result.findings)


def test_all_empty_statistics() -> None:
    repos = [_repo("empty"), _repo("also-empty")]
    languages = {
        "octocat/empty": _language_stats(),
        "octocat/also-empty": _language_stats(),
    }
    result = assess_language_distribution(_snapshot(repos, languages=languages))

    assert result.total_bytes == 0
    assert result.empty_count == 2
    assert result.dominant_language is None
    assert any(f.id == "languages.no_data" for f in result.findings)
    assert not any(f.id == "languages.coverage_gap" for f in result.findings)


def test_no_repositories() -> None:
    result = assess_language_distribution(_snapshot([]))

    assert result.repositories == []
    assert result.distribution == []
    assert _metric(result, "languages.repos.total") == 0
    finding = next(f for f in result.findings if f.id == "languages.no_repositories")
    assert finding.severity is FindingSeverity.INFO
