"""Unit tests for the recommendation engine (issue #52).

Covers finding-to-recommendation mapping (templating, severity, effort,
priority, evidence), low-score recommendations with their severity bands, plan
ordering and finding back-links.
"""

from __future__ import annotations

import pytest

from ghdtk.models.derived import (
    DimensionId,
    DimensionScore,
    Finding,
    FindingSeverity,
    Recommendation,
    RecommendationEffort,
    RecommendationPriority,
    ScoreBreakdown,
    SourceEntityKind,
    SourceReference,
)
from ghdtk.recommendations.engine import (
    RecommendationEngine,
    backfill_finding_links,
    order_key,
)


def _source(identifier: str = "octocat") -> SourceReference:
    return SourceReference(entity=SourceEntityKind.USER, identifier=identifier, field="bio")


def _finding(
    finding_id: str,
    *,
    severity: FindingSeverity = FindingSeverity.LOW,
    title: str = "Finding",
) -> Finding:
    return Finding(
        id=finding_id,
        type="quality_issue",
        severity=severity,
        title=title,
        message="message",
        evidence=[_source()],
    )


def _score(dimension: DimensionId, score: float, weight: float = 1.0) -> DimensionScore:
    return DimensionScore(
        dimension=dimension,
        score=score,
        weight=weight,
        breakdown=[
            ScoreBreakdown(
                component_id="component",
                label="Component",
                weight=1.0,
                contribution=score,
                metric_id="metric.one",
                sources=[_source("octocat/repo")],
            )
        ],
    )


def test_finding_produces_templated_recommendation() -> None:
    finding = _finding("presence.name.missing", severity=FindingSeverity.MEDIUM)
    engine = RecommendationEngine()
    (recommendation,) = engine.recommend(username="octocat", findings=[finding])
    assert recommendation.template_id == "presence.field.missing"
    assert recommendation.action == "Add your name to your GitHub profile."
    assert recommendation.finding_ids == ["presence.name.missing"]
    assert recommendation.severity is FindingSeverity.MEDIUM
    assert recommendation.effort is RecommendationEffort.LOW
    assert recommendation.priority is RecommendationPriority.MEDIUM
    assert recommendation.metric_ids == ["presence.fields.missing"]
    assert recommendation.sources == [_source()]


def test_full_name_placeholder_rendered_from_prefix() -> None:
    finding = _finding("repo.quality.no_description.octocat/hello")
    engine = RecommendationEngine()
    (recommendation,) = engine.recommend(username="octocat", findings=[finding])
    assert recommendation.action == "Add a description to the octocat/hello repository."
    assert recommendation.id == "repo.add_description:repo.quality.no_description.octocat/hello"


def test_username_placeholder_rendered() -> None:
    finding = _finding("readme.no_profile_repo", title="No profile repository")
    engine = RecommendationEngine()
    (recommendation,) = engine.recommend(username="octocat", findings=[finding])
    assert recommendation.action == "Create a octocat/octocat repository with a README.md."


def test_disclosure_and_positive_findings_produce_no_recommendation() -> None:
    engine = RecommendationEngine()
    findings = [
        _finding("network.followers.growth_unavailable"),
        _finding("star_growth.rising"),
        _finding("presence.name.missing"),
    ]
    recommendations = engine.recommend(username="octocat", findings=findings)
    assert len(recommendations) == 1
    assert recommendations[0].finding_ids == ["presence.name.missing"]


def test_low_score_produces_recommendation() -> None:
    engine = RecommendationEngine()
    score = _score(DimensionId.PRESENCE, 25.0)
    (recommendation,) = engine.recommend(username="octocat", findings=[], scores=[score])
    assert recommendation.template_id == "dimension.low_score"
    assert recommendation.id == "low_score:presence"
    assert recommendation.priority is RecommendationPriority.MEDIUM
    assert recommendation.severity is FindingSeverity.MEDIUM
    assert recommendation.action == "Work on improving your Profile presence dimension."
    assert recommendation.metric_ids == ["metric.one"]
    assert recommendation.sources == [_source("octocat/repo")]


def test_low_score_severity_bands() -> None:
    engine = RecommendationEngine()
    bands = [
        (_score(DimensionId.PRESENCE, 15.0), RecommendationPriority.HIGH, FindingSeverity.HIGH),
        (_score(DimensionId.ACTIVITY, 30.0), RecommendationPriority.MEDIUM, FindingSeverity.MEDIUM),
        (_score(DimensionId.CONSISTENCY, 38.0), RecommendationPriority.LOW, FindingSeverity.LOW),
    ]
    for score, priority, severity in bands:
        (recommendation,) = engine.recommend(username="octocat", scores=[score])
        assert recommendation.priority is priority
        assert recommendation.severity is severity


def test_score_above_threshold_produces_no_recommendation() -> None:
    engine = RecommendationEngine()
    recommendations = engine.recommend(
        username="octocat",
        scores=[_score(DimensionId.PRESENCE, 60.0)],
    )
    assert recommendations == []


def test_empty_inputs_produce_no_recommendations() -> None:
    engine = RecommendationEngine()
    assert engine.recommend(username="octocat") == []


def test_plan_order_priority_then_effort_then_id() -> None:
    engine = RecommendationEngine()
    findings = [
        _finding("presence.hireable.unset"),  # LOW effort, MEDIUM priority
        _finding("presence.account.recent"),  # MEDIUM effort, LOW priority
        _finding("readme.boilerplate"),  # MEDIUM effort, HIGH priority
    ]
    recommendations = engine.recommend(username="octocat", findings=findings)
    ids = [r.template_id for r in recommendations]
    assert ids == [
        "readme.replace_boilerplate",
        "presence.set_hireable",
        "presence.build_history",
    ]


def test_plan_order_tie_breaks_on_id() -> None:
    engine = RecommendationEngine()
    findings = [
        _finding("presence.company.missing"),
        _finding("presence.name.missing"),
    ]
    recommendations = engine.recommend(username="octocat", findings=findings)
    ids = [r.id for r in recommendations]
    assert ids == [
        "presence.field.missing:presence.company.missing",
        "presence.field.missing:presence.name.missing",
    ]


def test_order_key_ranks_high_before_low_and_low_effort_first() -> None:
    high = _recommendation("b", RecommendationPriority.HIGH, RecommendationEffort.HIGH)
    mid = _recommendation("a", RecommendationPriority.MEDIUM, RecommendationEffort.LOW)
    assert order_key(high) < order_key(mid)
    low_effort = _recommendation("a", RecommendationPriority.MEDIUM, RecommendationEffort.LOW)
    high_effort = _recommendation("a", RecommendationPriority.MEDIUM, RecommendationEffort.HIGH)
    assert order_key(low_effort) < order_key(high_effort)


def _recommendation(
    rec_id: str,
    priority: RecommendationPriority,
    effort: RecommendationEffort,
) -> Recommendation:
    return Recommendation(
        id=rec_id,
        priority=priority,
        action="a",
        rationale="r",
        effort=effort,
    )


def test_backfill_finding_links() -> None:
    engine = RecommendationEngine()
    findings = [
        _finding("presence.name.missing", title="Missing name"),
        _finding("network.followers.growth_unavailable", title="Growth unavailable"),
    ]
    recommendations = engine.recommend(username="octocat", findings=findings)
    linked = backfill_finding_links(findings, recommendations)
    assert linked[0].recommendation_ids == [r.id for r in recommendations]
    assert linked[1].recommendation_ids == []
    assert findings[0].recommendation_ids == []


@pytest.mark.parametrize("score", [0.0, 100.0])
def test_recommendations_never_panic_on_boundary_scores(score: float) -> None:
    engine = RecommendationEngine()
    score_breakdown = _score(DimensionId.ACTIVITY, score)
    recommendations = engine.recommend(username="octocat", scores=[score_breakdown])
    if score == 100.0:
        assert recommendations == []
    else:
        assert len(recommendations) == 1
