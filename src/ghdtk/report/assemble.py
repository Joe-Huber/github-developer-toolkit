"""Analysis report data assembly (issue #55).

``ReportAssembler`` runs the complete analysis pipeline for one profile and
composes the result into the :class:`~ghdtk.models.derived.Report` DTO:

``raw snapshot -> analyzers -> metrics & findings -> scoring -> overall ->
recommendations -> synthesis -> Report``

The pipeline is deterministic for a fixed snapshot and clock: analyzer order,
metric/finding ordering and every ranking are fixed, and the ``now`` clock is
passed through so nothing depends on wall-clock time. The profile README is an
optional collection artifact; when it is absent the readme analysis is skipped
and reported as ``None`` rather than guessed.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol

from ghdtk.analyzers import (
    AnalysisThresholds,
    assess_commit_activity,
    assess_contribution_calendar,
    assess_follower_network,
    assess_issue_participation,
    assess_language_distribution,
    assess_portfolio_composition,
    assess_profile_presence,
    assess_pull_request_collaboration,
    assess_readme_quality,
    assess_repository_activity,
    assess_repository_quality,
    assess_star_distribution,
    assess_star_growth,
    assess_technology_diversity,
)
from ghdtk.models.derived import (
    Finding,
    MetricRecord,
    ProfileAnalyses,
    ProfileAnalysis,
    Report,
)
from ghdtk.models.derived.analyses import ensure_built
from ghdtk.models.raw import ProfileReadme, ProfileSnapshot
from ghdtk.recommendations.engine import RecommendationEngine
from ghdtk.recommendations.synthesis import synthesize
from ghdtk.scoring.aggregate import aggregate_dimension_scores
from ghdtk.scoring.framework import ScoreInputs, ScoringConfig, ScoringRegistry
from ghdtk.scoring.scorers import default_scorers

__all__ = ["ReportAssembler", "run_analyses"]

ensure_built()


class _AnalysisWithLists(Protocol):
    """Any analyzer result carrying derived metrics and findings."""

    metrics: list[MetricRecord]
    findings: list[Finding]


def run_analyses(
    username: str,
    snapshot: ProfileSnapshot,
    *,
    now: datetime,
    profile_readme: ProfileReadme | None = None,
    thresholds: AnalysisThresholds | None = None,
    domain_map: Mapping[str, str] | None = None,
) -> ProfileAnalyses:
    """Run every analyzer over the snapshot in canonical order.

    Analyses whose inputs are missing (no user, no profile README) are reported
    as ``None`` so downstream layers never fabricate data.
    """
    thresholds = thresholds or AnalysisThresholds()
    presence = assess_profile_presence(snapshot.user, now=now) if snapshot.user else None
    readme = assess_readme_quality(profile_readme, now=now) if profile_readme else None
    return ProfileAnalyses(
        presence=presence,
        readme=readme,
        repository_quality=assess_repository_quality(snapshot, thresholds=thresholds),
        repository_activity=assess_repository_activity(snapshot, now=now, thresholds=thresholds),
        portfolio=assess_portfolio_composition(snapshot, now=now, thresholds=thresholds),
        stars=assess_star_distribution(snapshot, thresholds=thresholds),
        star_growth=assess_star_growth(snapshot, now=now, thresholds=thresholds),
        network=assess_follower_network(snapshot, thresholds=thresholds),
        commits=assess_commit_activity(snapshot, thresholds=thresholds),
        contribution_calendar=assess_contribution_calendar(snapshot, thresholds=thresholds),
        pull_requests=assess_pull_request_collaboration(snapshot, thresholds=thresholds),
        issues=assess_issue_participation(snapshot, thresholds=thresholds),
        languages=assess_language_distribution(snapshot, thresholds=thresholds),
        technology=assess_technology_diversity(
            snapshot, thresholds=thresholds, domain_map=domain_map
        ),
    )


def _present(analyses: ProfileAnalyses) -> list[_AnalysisWithLists]:
    """Present analyses in canonical field order."""
    result: list[_AnalysisWithLists] = []
    for name in ProfileAnalyses.model_fields:
        analysis = getattr(analyses, name)
        if analysis is not None:
            result.append(analysis)
    return result


def _flatten_metrics(analyses: ProfileAnalyses) -> list[MetricRecord]:
    metrics: list[MetricRecord] = []
    for analysis in _present(analyses):
        metrics.extend(analysis.metrics)
    return metrics


def _flatten_findings(analyses: ProfileAnalyses) -> list[Finding]:
    findings: list[Finding] = []
    for analysis in _present(analyses):
        findings.extend(analysis.findings)
    return findings


def _normalize_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class ReportAssembler:
    """Assembles a complete :class:`Report` from a raw snapshot."""

    def __init__(
        self,
        *,
        thresholds: AnalysisThresholds | None = None,
        config: ScoringConfig | None = None,
        registry: ScoringRegistry | None = None,
        engine: RecommendationEngine | None = None,
        domain_map: Mapping[str, str] | None = None,
    ) -> None:
        self.thresholds = thresholds or AnalysisThresholds()
        self.config = config or ScoringConfig()
        self.registry = registry or ScoringRegistry(
            default_scorers(self.config), config=self.config
        )
        self.engine = engine or RecommendationEngine(self.config)
        self.domain_map = domain_map

    def assemble(
        self,
        *,
        username: str,
        snapshot: ProfileSnapshot,
        now: datetime | None = None,
        profile_readme: ProfileReadme | None = None,
    ) -> Report:
        """Run the analysis pipeline and compose the report DTO.

        ``now`` defaults to the snapshot's collection time so a snapshot always
        assembles to the same report regardless of when it is rendered.
        """
        now = _normalize_now(now or snapshot.collected_at)
        analyses = run_analyses(
            username,
            snapshot,
            now=now,
            profile_readme=profile_readme,
            thresholds=self.thresholds,
            domain_map=self.domain_map,
        )
        metrics = _flatten_metrics(analyses)
        findings = _flatten_findings(analyses)
        scores = self.registry.score_all(self._inputs(analyses))
        overall = aggregate_dimension_scores(scores, self.config)
        recommendations = self.engine.recommend(username=username, findings=findings, scores=scores)
        synthesis = synthesize(findings=findings, overall=overall, recommendations=recommendations)
        return Report(
            generated_at=now,
            profile=ProfileAnalysis(
                username=username,
                analyzed_at=now,
                analyses=analyses,
                metrics=metrics,
                scores=scores,
                overall=overall,
                findings=findings,
                recommendations=recommendations,
                synthesis=synthesis,
            ),
        )

    def _inputs(self, analyses: ProfileAnalyses) -> ScoreInputs:
        return ScoreInputs(
            presence=analyses.presence,
            readme=analyses.readme,
            repository_quality=analyses.repository_quality,
            repository_activity=analyses.repository_activity,
            portfolio=analyses.portfolio,
            stars=analyses.stars,
            network=analyses.network,
            commits=analyses.commits,
            contribution_calendar=analyses.contribution_calendar,
            pull_requests=analyses.pull_requests,
            languages=analyses.languages,
        )
