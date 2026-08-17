"""Tests for technology diversity & dominant-area analysis (issue #45)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ghdtk.analyzers.technology import (
    DEFAULT_DOMAIN_MAP,
    TechnologyDiversityAnalysis,
    assess_technology_diversity,
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


def _metric(result: TechnologyDiversityAnalysis, metric_id: str) -> MetricValue:
    return next(metric.value for metric in result.metrics if metric.id == metric_id)


def _availability(result: TechnologyDiversityAnalysis, metric_id: str) -> MetricAvailability:
    return next(metric.availability for metric in result.metrics if metric.id == metric_id)


def test_generalist_profile_from_fixture(load_raw_fixture: Any) -> None:
    snapshot = ProfileSnapshot.model_validate(load_raw_fixture("languages_generalist"))
    result = assess_technology_diversity(snapshot)

    assert result.total_bytes == 65_000
    assert result.mapped_bytes == 65_000
    assert result.unmapped_bytes == 0
    assert result.mapped_share == 1.0
    assert result.unmapped_share == 0.0
    assert result.domains_count == 4
    assert result.simpson_index == 0.75
    assert result.top_domain == "infrastructure"
    assert result.top_domain_share == 0.31
    assert result.topic_presence == {"data": 1, "mobile": 1, "web": 1, "infrastructure": 2}

    shares = {entry.domain: entry for entry in result.domain_shares}
    assert shares["infrastructure"].bytes == 20_000
    assert shares["infrastructure"].share == 0.31
    assert shares["web"].share == 0.23
    assert shares["data"].share == 0.23
    assert shares["mobile"].share == 0.23
    assert shares["web"].language_repositories == ["octocat/web"]
    assert shares["data"].topic_repositories == ["octocat/data"]

    assert _metric(result, "tech.simpson_index") == 0.75
    assert _metric(result, "tech.top_domain") == "infrastructure"
    assert _metric(result, "tech.top_domain_share") == 0.31
    assert _metric(result, "tech.domains_count") == 4
    assert _metric(result, "tech.mapped_share") == 1.0
    assert _metric(result, "tech.unmapped_share") == 0.0
    assert _metric(result, "tech.domain_share.infrastructure") == 0.31
    assert _metric(result, "tech.domain_bytes.infrastructure") == 20_000
    assert _metric(result, "tech.topics.web") == 1

    diverse = next(f for f in result.findings if f.id == "tech.diverse")
    assert diverse.severity is FindingSeverity.INFO
    assert diverse.dimension is DimensionId.CODE_QUALITY
    assert "0.75" in diverse.message

    assert not any(f.id == "tech.specialized" for f in result.findings)
    assert not any(f.id == "tech.low_mapping_coverage" for f in result.findings)
    assert not any(f.id == "tech.no_evidence" for f in result.findings)


def test_specialist_profile_from_fixture(load_raw_fixture: Any) -> None:
    snapshot = ProfileSnapshot.model_validate(load_raw_fixture("languages_specialist"))
    result = assess_technology_diversity(snapshot)

    assert result.total_bytes == 80_000
    assert result.mapped_share == 1.0
    assert result.domains_count == 1
    assert result.simpson_index == 0.0
    assert result.top_domain == "data"
    assert result.top_domain_share == 1.0
    assert result.topic_presence == {"data": 2}

    assert _metric(result, "tech.simpson_index") == 0.0
    assert _metric(result, "tech.top_domain") == "data"
    assert _metric(result, "tech.top_domain_share") == 1.0
    assert _metric(result, "tech.topics.data") == 2

    specialized = next(f for f in result.findings if f.id == "tech.specialized")
    assert specialized.severity is FindingSeverity.INFO
    assert "data" in specialized.title
    assert any(ref.identifier == "octocat/ml" for ref in specialized.evidence)
    assert any(
        ref.identifier == "octocat/etl" and ref.field == "topics" for ref in specialized.evidence
    )

    assert not any(f.id == "tech.diverse" for f in result.findings)


def test_domain_map_is_configurable() -> None:
    repos = [_repo("a"), _repo("b")]
    languages = {
        "octocat/a": _language_stats(Python=10_000),
        "octocat/b": _language_stats(JavaScript=10_000),
    }
    default = assess_technology_diversity(_snapshot(repos, languages=languages))
    assert default.top_domain in {"data", "web"}
    assert default.simpson_index == 0.5

    custom = assess_technology_diversity(
        _snapshot(repos, languages=languages),
        domain_map={"Python": "web", "JavaScript": "web"},
    )
    assert custom.top_domain == "web"
    assert custom.top_domain_share == 1.0
    assert custom.simpson_index == 0.0
    assert any(f.id == "tech.specialized" for f in custom.findings)


def test_unmapped_languages_are_disclosed() -> None:
    repos = [_repo("a"), _repo("b"), _repo("c")]
    languages = {
        "octocat/a": _language_stats(Python=4_000),
        "octocat/b": _language_stats(JavaScript=4_000),
        "octocat/c": _language_stats(COBOL=2_000),
    }
    result = assess_technology_diversity(_snapshot(repos, languages=languages))

    assert result.total_bytes == 10_000
    assert result.mapped_bytes == 8_000
    assert result.unmapped_bytes == 2_000
    assert result.mapped_share == 0.8
    assert result.unmapped_share == 0.2
    assert result.simpson_index == 0.5
    assert _metric(result, "tech.unmapped_share") == 0.2
    assert not any(f.id == "tech.low_mapping_coverage" for f in result.findings)


def test_low_mapping_coverage_threshold_is_config_driven() -> None:
    repos = [_repo("a"), _repo("b")]
    languages = {
        "octocat/a": _language_stats(Python=1_000),
        "octocat/b": _language_stats(COBOL=9_000),
    }
    default = assess_technology_diversity(_snapshot(repos, languages=languages))
    assert default.mapped_share == 0.1
    finding = next(f for f in default.findings if f.id == "tech.low_mapping_coverage")
    assert "90%" in finding.message
    assert any(ref.identifier == "octocat/b" for ref in finding.evidence)

    lenient = assess_technology_diversity(
        _snapshot(repos, languages=languages),
        thresholds=AnalysisThresholds(technology_mapping_coverage_threshold=0.05),
    )
    assert not any(f.id == "tech.low_mapping_coverage" for f in lenient.findings)


def test_specialization_threshold_is_config_driven() -> None:
    repos = [_repo("a"), _repo("b")]
    languages = {
        "octocat/a": _language_stats(TypeScript=6_000),
        "octocat/b": _language_stats(Python=4_000),
    }
    default = assess_technology_diversity(_snapshot(repos, languages=languages))
    assert default.top_domain == "web"
    assert default.top_domain_share == 0.6
    assert any(f.id == "tech.specialized" for f in default.findings)
    assert not any(f.id == "tech.diverse" for f in default.findings)

    strict = assess_technology_diversity(
        _snapshot(repos, languages=languages),
        thresholds=AnalysisThresholds(technology_specialization_threshold=0.7),
    )
    assert not any(f.id == "tech.specialized" for f in strict.findings)


def test_diversity_threshold_is_config_driven(load_raw_fixture: Any) -> None:
    snapshot = ProfileSnapshot.model_validate(load_raw_fixture("languages_generalist"))
    default = assess_technology_diversity(snapshot)
    assert any(f.id == "tech.diverse" for f in default.findings)

    strict = assess_technology_diversity(
        snapshot,
        thresholds=AnalysisThresholds(technology_diversity_threshold=0.9),
    )
    assert not any(f.id == "tech.diverse" for f in strict.findings)


def test_topics_only_profile() -> None:
    repos = [_repo("infra", topics=["docker", "kubernetes"])]
    result = assess_technology_diversity(_snapshot(repos))

    assert result.total_bytes == 0
    assert result.simpson_index is None
    assert result.domains_count == 0
    assert result.topic_presence == {"infrastructure": 2}
    assert _metric(result, "tech.simpson_index") is None
    assert _availability(result, "tech.simpson_index") is MetricAvailability.UNAVAILABLE
    assert _metric(result, "tech.topics.infrastructure") == 2

    finding = next(f for f in result.findings if f.id == "tech.no_byte_evidence")
    assert finding.severity is FindingSeverity.INFO
    assert any(
        ref.identifier == "octocat/infra" and ref.field == "topics" for ref in finding.evidence
    )
    assert not any(f.id == "tech.no_evidence" for f in result.findings)


def test_no_evidence() -> None:
    result = assess_technology_diversity(_snapshot([]))

    assert result.total_bytes == 0
    assert result.simpson_index is None
    assert result.domains_count == 0
    assert _metric(result, "tech.simpson_index") is None
    assert _availability(result, "tech.simpson_index") is MetricAvailability.UNAVAILABLE
    finding = next(f for f in result.findings if f.id == "tech.no_evidence")
    assert finding.severity is FindingSeverity.INFO


def test_default_domain_map_covers_languages_and_topics() -> None:
    assert DEFAULT_DOMAIN_MAP["Python"] == "data"
    assert DEFAULT_DOMAIN_MAP["TypeScript"] == "web"
    assert DEFAULT_DOMAIN_MAP["Kotlin"] == "mobile"
    assert DEFAULT_DOMAIN_MAP["Dockerfile"] == "infrastructure"
    assert DEFAULT_DOMAIN_MAP["Docker"] == "infrastructure"
    assert DEFAULT_DOMAIN_MAP["Kubernetes"] == "infrastructure"
    assert DEFAULT_DOMAIN_MAP["Java"] == "backend"
