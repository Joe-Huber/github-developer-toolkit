"""Unit tests for derived analysis data models (see issue #15).

Verifies that metrics, scores, findings, recommendations and the report DTO
round-trip through JSON losslessly, carry provenance, and enforce value
bounds.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ghdtk.models.derived import (
    DimensionId,
    DimensionScore,
    Finding,
    FindingSeverity,
    MetricRecord,
    ProfileAnalysis,
    Recommendation,
    RecommendationEffort,
    RecommendationPriority,
    Report,
    ScoreBreakdown,
    SourceEntityKind,
    SourceReference,
)


def _source(entity: SourceEntityKind = SourceEntityKind.REPOSITORY) -> SourceReference:
    return SourceReference(
        entity=entity, identifier="octocat/Hello-World", field="stargazers_count"
    )


def _metric(value: int | float | bool | str | None = 80) -> MetricRecord:
    return MetricRecord(
        id="repo.stars",
        label="Stars across public repositories",
        value=value,
        sources=[_source()],
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        confidence=0.95,
    )


def _score() -> DimensionScore:
    return DimensionScore(
        dimension=DimensionId.PRESENCE,
        score=72.5,
        weight=0.2,
        rationale="Profile completeness is solid.",
        breakdown=[
            ScoreBreakdown(
                component_id="bio.present",
                label="Bio present",
                weight=0.5,
                contribution=40.0,
                metric_id="profile.bio_present",
                sources=[
                    SourceReference(
                        entity=SourceEntityKind.USER,
                        identifier="octocat",
                        field="bio",
                    )
                ],
            )
        ],
    )


def _finding() -> Finding:
    return Finding(
        id="f1",
        type="stale_repository",
        severity=FindingSeverity.MEDIUM,
        title="Repository has been inactive",
        message="octocat/Hello-World has no commits in 90 days.",
        dimension=DimensionId.ACTIVITY,
        evidence=[_source()],
        recommendation_ids=["r1"],
    )


def _recommendation() -> Recommendation:
    return Recommendation(
        id="r1",
        priority=RecommendationPriority.HIGH,
        action="Push a commit to octocat/Hello-World.",
        rationale="Recent activity improves the activity dimension score.",
        template_id="repo.stale_repository",
        severity=FindingSeverity.LOW,
        effort=RecommendationEffort.LOW,
        finding_ids=["f1"],
        metric_ids=["repo.stars"],
        sources=[_source()],
    )


def _report() -> Report:
    return Report(
        generated_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        profile=ProfileAnalysis(
            username="octocat",
            analyzed_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            metrics=[_metric()],
            scores=[_score()],
            findings=[_finding()],
            recommendations=[_recommendation()],
        ),
    )


# --- metric ----------------------------------------------------------------


def test_metric_roundtrip() -> None:
    loaded = MetricRecord.model_validate_json(_metric().model_dump_json())
    assert loaded == _metric()
    assert loaded.value == 80


@pytest.mark.parametrize("value", [42, 3.14, True, "hello", None])
def test_metric_value_types_roundtrip(value: int | float | bool | str | None) -> None:
    metric = _metric(value)
    loaded = MetricRecord.model_validate_json(metric.model_dump_json())
    assert loaded == metric
    assert loaded.value == value


@pytest.mark.parametrize("confidence", [-0.1, 1.5])
def test_metric_confidence_bounds(confidence: float) -> None:
    data = _metric().model_dump()
    data["confidence"] = confidence
    with pytest.raises(ValidationError):
        MetricRecord.model_validate(data)


# --- scores ----------------------------------------------------------------


def test_score_roundtrip() -> None:
    loaded = DimensionScore.model_validate_json(_score().model_dump_json())
    assert loaded == _score()
    assert loaded.dimension is DimensionId.PRESENCE
    assert loaded.breakdown[0].sources[0].entity is SourceEntityKind.USER


def test_score_bounds() -> None:
    with pytest.raises(ValidationError):
        DimensionScore(dimension=DimensionId.PRESENCE, score=150.0, weight=1.0)


def test_score_breakdown_negative_weight_rejected() -> None:
    with pytest.raises(ValidationError):
        ScoreBreakdown(component_id="c", label="c", weight=-1.0, contribution=0.0)


# --- findings --------------------------------------------------------------


def test_finding_roundtrip() -> None:
    loaded = Finding.model_validate_json(_finding().model_dump_json())
    assert loaded == _finding()
    assert loaded.severity is FindingSeverity.MEDIUM
    assert loaded.recommendation_ids == ["r1"]


# --- recommendations -------------------------------------------------------


def test_recommendation_roundtrip() -> None:
    loaded = Recommendation.model_validate_json(_recommendation().model_dump_json())
    assert loaded == _recommendation()
    assert loaded.priority is RecommendationPriority.HIGH
    assert loaded.template_id == "repo.stale_repository"
    assert loaded.severity is FindingSeverity.LOW
    assert loaded.effort is RecommendationEffort.LOW
    assert loaded.metric_ids == ["repo.stars"]


# --- report / snapshot -----------------------------------------------------


def test_report_roundtrip() -> None:
    loaded = Report.model_validate_json(_report().model_dump_json())
    assert loaded == _report()
    assert loaded.tool_version == "0.1.0"
    assert loaded.profile.username == "octocat"
    assert loaded.profile.metrics[0].sources[0].entity is SourceEntityKind.REPOSITORY


def test_profile_analysis_defaults_empty() -> None:
    analysis = ProfileAnalysis(username="octocat", analyzed_at=datetime(2026, 1, 1, tzinfo=UTC))
    assert analysis.metrics == []
    assert analysis.scores == []
    assert analysis.findings == []
    assert analysis.recommendations == []
    assert analysis.schema_version == 1


def test_report_matches_analysis_content() -> None:
    report = _report()
    dumped = report.model_dump()
    assert dumped["profile"]["username"] == "octocat"
    assert dumped["profile"]["metrics"][0]["value"] == 80


# --- provenance ------------------------------------------------------------


def test_source_reference_immutable() -> None:
    ref = _source()
    with pytest.raises(ValidationError):
        ref.identifier = "other"  # type: ignore[misc]


def test_source_reference_roundtrip() -> None:
    ref = _source()
    loaded = SourceReference.model_validate_json(ref.model_dump_json())
    assert loaded == ref
    assert loaded.field == "stargazers_count"
