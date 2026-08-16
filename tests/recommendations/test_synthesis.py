"""Unit tests for the profile synthesis (issue #53).

Covers the deterministic assembly of strengths, weaknesses, red flags and the
prioritized plan from findings, the overall score and recommendations.
"""

from __future__ import annotations

from ghdtk.models.derived import (
    Finding,
    FindingSeverity,
    OverallScore,
    Recommendation,
    RecommendationEffort,
    RecommendationPriority,
    SourceEntityKind,
    SourceReference,
    Synthesis,
)
from ghdtk.recommendations.synthesis import synthesize


def _finding(
    finding_id: str,
    *,
    finding_type: str = "quality_issue",
    severity: FindingSeverity = FindingSeverity.LOW,
    title: str = "Title",
) -> Finding:
    return Finding(
        id=finding_id,
        type=finding_type,
        severity=severity,
        title=title,
        message="message",
        evidence=[SourceReference(entity=SourceEntityKind.USER, identifier="octocat")],
    )


def _overall(strengths: list[str], weaknesses: list[str]) -> OverallScore:
    return OverallScore(
        overall=64.0,
        contributions=[],
        strengths=strengths,
        weaknesses=weaknesses,
    )


def _recommendation(
    rec_id: str,
    priority: RecommendationPriority,
    effort: RecommendationEffort = RecommendationEffort.MEDIUM,
) -> Recommendation:
    return Recommendation(id=rec_id, priority=priority, action="a", rationale="r", effort=effort)


def test_synthesis_assembles_all_sections() -> None:
    findings = [
        _finding(
            "repo.standout.octocat/hello",
            finding_type="standout",
            title="Standout repository",
        ),
        _finding(
            "commit_activity.consistent_cadence",
            finding_type="standout",
            title="Consistent cadence",
        ),
        _finding(
            "repo.activity.stale.octocat/hello",
            finding_type="quality_issue",
            title="Stale repository",
        ),
        _finding("presence.name.missing", finding_type="missing_information", title="Missing name"),
        _finding(
            "star_growth.insufficient_data",
            finding_type="informational",
            title="Star growth cannot be assessed",
        ),
    ]
    synthesis = synthesize(
        findings=findings,
        overall=_overall(strengths=["Open source (85/100)"], weaknesses=["Consistency (35/100)"]),
        recommendations=[
            _recommendation("r-stale", RecommendationPriority.MEDIUM),
            _recommendation("r-high", RecommendationPriority.HIGH),
        ],
    )
    assert synthesis.strengths == [
        "Open source (85/100)",
        "Consistent cadence",
        "Standout repository",
    ]
    assert synthesis.weaknesses == ["Consistency (35/100)", "Stale repository"]
    assert synthesis.red_flags == ["Missing name", "Star growth cannot be assessed"]


def test_placeholder_findings_are_red_flags() -> None:
    synthesis = synthesize(
        findings=[
            _finding(
                "presence.bio.placeholder",
                finding_type="placeholder_value",
                title="Placeholder bio",
            )
        ]
    )
    assert synthesis.red_flags == ["Placeholder bio"]
    assert synthesis.weaknesses == []
    assert synthesis.strengths == []


def test_plan_orders_by_priority_then_effort_then_id() -> None:
    recommendations = [
        _recommendation("low-a", RecommendationPriority.LOW),
        _recommendation("high-b", RecommendationPriority.HIGH),
        _recommendation("high-a", RecommendationPriority.HIGH, RecommendationEffort.LOW),
    ]
    synthesis = synthesize(findings=[], recommendations=recommendations)
    assert [r.id for r in synthesis.plan] == ["high-a", "high-b", "low-a"]


def test_synthesis_is_deterministic() -> None:
    findings = [
        _finding("repo.standout.x", finding_type="standout", title="X"),
        _finding("presence.name.missing", finding_type="missing_information", title="Missing"),
        _finding("repo.activity.stale.x", finding_type="quality_issue", title="Stale"),
    ]
    first = synthesize(findings=findings, overall=_overall(["A"], ["B"]))
    second = synthesize(findings=list(reversed(findings)), overall=_overall(["A"], ["B"]))
    assert first == second


def test_empty_assessment_produces_empty_synthesis() -> None:
    synthesis = synthesize(findings=[], recommendations=[])
    assert synthesis == Synthesis()


def test_overall_only_strengths() -> None:
    synthesis = synthesize(findings=[], overall=_overall(["Visibility (90/100)"], []))
    assert synthesis.strengths == ["Visibility (90/100)"]
    assert synthesis.weaknesses == []
