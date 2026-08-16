"""Recommendation engine (issue #52).

Turns findings and low dimension scores into actionable, evidence-backed
recommendations. Every recommendation:

- comes from a templated rule (``template_id``),
- references the finding(s) that triggered it (``finding_ids``),
- carries the severity of the underlying evidence (``severity``),
- carries the provenance of that evidence (``sources``),
- is categorized by impact (``priority``) and estimated ``effort``.

Recommendations are returned in the plan order used by the synthesis: highest
priority first, and within a priority the lowest-effort quick wins first.
"""

from __future__ import annotations

from collections.abc import Sequence

from ghdtk.models.derived import (
    DimensionScore,
    Finding,
    FindingSeverity,
    Recommendation,
    RecommendationEffort,
    RecommendationPriority,
)
from ghdtk.recommendations.rules import RecommendationRule, extract_value, match_rule
from ghdtk.scoring.framework import ScoringConfig, dedupe_sources, dimension_label

_LOW_SCORE_TEMPLATE_ID = "dimension.low_score"

_LOW_SCORE_EFFORT: dict[str, RecommendationEffort] = {
    "presence": RecommendationEffort.LOW,
    "code_quality": RecommendationEffort.MEDIUM,
    "consistency": RecommendationEffort.MEDIUM,
    "activity": RecommendationEffort.MEDIUM,
    "contribution": RecommendationEffort.MEDIUM,
    "engagement": RecommendationEffort.MEDIUM,
    "open_source": RecommendationEffort.MEDIUM,
    "visibility": RecommendationEffort.MEDIUM,
}

_SEVERITY_BANDS: tuple[tuple[float, FindingSeverity, RecommendationPriority], ...] = (
    (20.0, FindingSeverity.HIGH, RecommendationPriority.HIGH),
    (35.0, FindingSeverity.MEDIUM, RecommendationPriority.MEDIUM),
    (100.0, FindingSeverity.LOW, RecommendationPriority.LOW),
)

PRIORITY_RANK = {
    RecommendationPriority.HIGH: 0,
    RecommendationPriority.MEDIUM: 1,
    RecommendationPriority.LOW: 2,
}

EFFORT_RANK = {
    RecommendationEffort.LOW: 0,
    RecommendationEffort.MEDIUM: 1,
    RecommendationEffort.HIGH: 2,
}


def order_key(recommendation: Recommendation) -> tuple[int, int, str]:
    """Sort key: priority (impact), then effort (quick wins first), then id."""
    return (
        PRIORITY_RANK[recommendation.priority],
        EFFORT_RANK[recommendation.effort],
        recommendation.id,
    )


class RecommendationEngine:
    """Generate recommendations from findings and low dimension scores."""

    def __init__(self, config: ScoringConfig | None = None) -> None:
        self.config = config or ScoringConfig()

    def recommend(
        self,
        *,
        username: str,
        findings: Sequence[Finding] = (),
        scores: Sequence[DimensionScore] = (),
    ) -> list[Recommendation]:
        """Build the prioritized recommendation list for a profile.

        Findings that map to an actionable rule produce one recommendation
        each; dimensions scored at or below ``config.weakness_threshold``
        produce a low-score recommendation. Disclosures and positive standouts
        are surfaced by the synthesis instead. The result is sorted in plan
        order.
        """
        recommendations: list[Recommendation] = []
        for finding in findings:
            rule = match_rule(finding.id)
            if rule is None:
                continue
            recommendations.append(self._from_finding(username, finding, rule))
        recommendations.extend(self._from_low_scores(scores))
        return sorted(recommendations, key=order_key)

    def _from_finding(
        self,
        username: str,
        finding: Finding,
        rule: RecommendationRule,
    ) -> Recommendation:
        values = {
            "username": username,
            "title": finding.title,
            **({rule.var: extract_value(rule, finding.id)} if rule.var else {}),
        }
        return Recommendation(
            id=f"{rule.id}:{finding.id}",
            template_id=rule.id,
            priority=rule.priority,
            action=rule.action.format(**values),
            rationale=rule.rationale.format(**values),
            severity=finding.severity,
            effort=rule.effort,
            finding_ids=[finding.id],
            metric_ids=list(rule.metrics),
            sources=dedupe_sources(list(finding.evidence)),
        )

    def _from_low_scores(self, scores: Sequence[DimensionScore]) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        for score in scores:
            if score.score > self.config.weakness_threshold:
                continue
            label = dimension_label(score.dimension)
            severity, priority = _band_for(score.score)
            metric_ids = [
                component.metric_id
                for component in score.breakdown
                if component.metric_id is not None
            ]
            sources = dedupe_sources(
                [ref for component in score.breakdown for ref in component.sources]
            )
            recommendations.append(
                Recommendation(
                    id=f"low_score:{score.dimension.value}",
                    template_id=_LOW_SCORE_TEMPLATE_ID,
                    priority=priority,
                    action=f"Work on improving your {label} dimension.",
                    rationale=(
                        f"{label} scored {score.score:.0f}/100, at or below the "
                        f"{self.config.weakness_threshold:.0f} weakness threshold."
                    ),
                    severity=severity,
                    effort=_LOW_SCORE_EFFORT.get(
                        score.dimension.value, RecommendationEffort.MEDIUM
                    ),
                    finding_ids=[],
                    metric_ids=metric_ids,
                    sources=sources,
                )
            )
        return recommendations


def _band_for(score: float) -> tuple[FindingSeverity, RecommendationPriority]:
    for limit, severity, priority in _SEVERITY_BANDS:
        if score <= limit:
            return severity, priority
    return FindingSeverity.LOW, RecommendationPriority.LOW


def backfill_finding_links(
    findings: Sequence[Finding],
    recommendations: Sequence[Recommendation],
) -> list[Finding]:
    """Return findings with ``recommendation_ids`` backfilled.

    Findings are frozen; each is copied with its recommendation links filled in
    from the recommendations that reference it, so the data stays consistent
    and the model stays immutable.
    """
    links: dict[str, list[str]] = {}
    for recommendation in recommendations:
        for finding_id in recommendation.finding_ids:
            links.setdefault(finding_id, []).append(recommendation.id)
    return [
        finding.model_copy(update={"recommendation_ids": sorted(links.get(finding.id, []))})
        for finding in findings
    ]
