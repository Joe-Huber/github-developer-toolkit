"""Scoring framework.

Defines the scorer interface, the :class:`ScoreInputs` container that carries
derived analyzer outputs into the scorers, the configurable
:class:`ScoringConfig`, and the :class:`ScoringRegistry` that runs a
collection of scorers over one profile's inputs (issue #47).

Every dimension scorer returns a :class:`~ghdtk.models.derived.DimensionScore`
whose breakdown records, for each weighted component, the contribution and the
raw/derived values (metric ids and provenance) that produced it, so every
score stays explainable from its inputs.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ghdtk.analyzers.commits import CommitActivity
from ghdtk.analyzers.contribution_calendar import ContributionCalendarAnalysis
from ghdtk.analyzers.languages import LanguageDistributionAnalysis
from ghdtk.analyzers.network import FollowerNetwork
from ghdtk.analyzers.portfolio import PortfolioComposition
from ghdtk.analyzers.presence import ProfilePresence
from ghdtk.analyzers.pull_requests import PullRequestAnalysis
from ghdtk.analyzers.readme import ReadmeAssessment
from ghdtk.analyzers.repository_activity import RepositoryActivity
from ghdtk.analyzers.repository_quality import RepositoryQuality
from ghdtk.analyzers.stars import StarsAnalysis
from ghdtk.models.derived import (
    DimensionId,
    DimensionScore,
    MetricRecord,
    MetricValue,
    SourceEntityKind,
    SourceReference,
)


class ScoreInputs(BaseModel):
    """All derived analyzer outputs a dimension scorer may consume.

    Fields are ``None`` when the corresponding analysis was not run or
    produced nothing. Each scorer documents whether a missing input means the
    dimension cannot be scored (the scorer returns ``None``, which the
    aggregation layer skips) or that the remaining components are re-normalized.
    """

    model_config = ConfigDict(frozen=True)

    presence: ProfilePresence | None = None
    readme: ReadmeAssessment | None = None
    repository_quality: RepositoryQuality | None = None
    repository_activity: RepositoryActivity | None = None
    portfolio: PortfolioComposition | None = None
    stars: StarsAnalysis | None = None
    network: FollowerNetwork | None = None
    commits: CommitActivity | None = None
    contribution_calendar: ContributionCalendarAnalysis | None = None
    pull_requests: PullRequestAnalysis | None = None
    languages: LanguageDistributionAnalysis | None = None


@runtime_checkable
class Scorer(Protocol):
    """A dimension scorer: turns :class:`ScoreInputs` into a 0-100 score."""

    dimension: ClassVar[DimensionId]
    label: ClassVar[str]

    def score(self, inputs: ScoreInputs) -> DimensionScore | None: ...


DIMENSION_LABELS: dict[DimensionId, str] = {
    DimensionId.PRESENCE: "Profile presence",
    DimensionId.CODE_QUALITY: "Code quality",
    DimensionId.CONSISTENCY: "Consistency",
    DimensionId.ACTIVITY: "Activity",
    DimensionId.CONTRIBUTION: "Contribution",
    DimensionId.ENGAGEMENT: "Community",
    DimensionId.OPEN_SOURCE: "Open source",
    DimensionId.VISIBILITY: "Visibility",
}


def dimension_label(dimension: DimensionId) -> str:
    """Human-readable label for a dimension."""
    return DIMENSION_LABELS.get(dimension, dimension.value)


def default_weights() -> dict[DimensionId, float]:
    """Default overall-aggregation weights per dimension.

    Activity, contribution and code quality carry slightly more weight than the
    presence/community/open-source/visibility dimensions.
    """
    return {
        DimensionId.PRESENCE: 1.0,
        DimensionId.CODE_QUALITY: 1.5,
        DimensionId.CONSISTENCY: 1.0,
        DimensionId.ACTIVITY: 1.5,
        DimensionId.CONTRIBUTION: 1.5,
        DimensionId.ENGAGEMENT: 1.0,
        DimensionId.OPEN_SOURCE: 1.0,
        DimensionId.VISIBILITY: 1.0,
    }


class ScoringConfig(BaseModel):
    """Configurable scoring weights and normalization parameters.

    Frozen and validated. Weights are non-negative: a weight of zero keeps a
    dimension's score available while excluding it from the overall
    aggregation. Parameters mirror the analysis defaults where they overlap.
    """

    model_config = ConfigDict(frozen=True)

    weights: dict[DimensionId, float] = Field(default_factory=default_weights)

    #: Commits per month at or above which cadence-based components get full
    #: credit (mirrors ``AnalysisThresholds.commit_cadence_per_month``).
    cadence_target: float = Field(default=4.0, ge=0.0)

    #: Median inter-commit gap (days) at or below which regularity is full credit.
    gap_good_days: int = Field(default=14, ge=1)

    #: Longest gap (days) at or beyond which consistency is zero credit.
    gap_bad_days: int = Field(default=60, ge=1)

    #: Volume targets for log-scaled components: the value at or above which a
    #: volume component reaches full credit.
    activity_volume_target: int = Field(default=1000, ge=1)
    contribution_volume_target: int = Field(default=5000, ge=1)
    star_volume_target: int = Field(default=5000, ge=1)
    follower_volume_target: int = Field(default=1000, ge=1)
    pr_volume_target: int = Field(default=300, ge=1)

    #: A dimension at or above this score counts as a strength.
    strength_threshold: float = Field(default=70.0, ge=0.0, le=100.0)

    #: A dimension at or below this score counts as a weakness.
    weakness_threshold: float = Field(default=40.0, ge=0.0, le=100.0)

    #: Maximum number of strengths and weaknesses reported.
    max_strengths: int = Field(default=3, ge=1)
    max_weaknesses: int = Field(default=3, ge=1)

    @classmethod
    def from_settings(cls, settings: object) -> ScoringConfig:
        """Build a config from a settings object's ``scoring_*`` fields.

        ``settings`` is duck-typed so the scoring layer does not import the
        config system directly: fields are read with ``getattr`` and only when
        present, leaving every other value at its default.
        """
        names = (
            "scoring_cadence_target",
            "scoring_gap_good_days",
            "scoring_gap_bad_days",
            "scoring_strength_threshold",
            "scoring_weakness_threshold",
        )
        values: dict[str, float | int] = {}
        for name in names:
            value = getattr(settings, name, None)
            if value is not None:
                values[name.removeprefix("scoring_")] = value
        return cls(**values)


class ScoringRegistry:
    """Runs a collection of dimension scorers over one profile's inputs."""

    def __init__(
        self,
        scorers: Sequence[Scorer],
        config: ScoringConfig | None = None,
    ) -> None:
        self.config = config or ScoringConfig()
        self._scorers = list(scorers)

    def dimensions(self) -> list[DimensionId]:
        """The dimensions this registry can score, in registration order."""
        return [scorer.dimension for scorer in self._scorers]

    def score_all(self, inputs: ScoreInputs) -> list[DimensionScore]:
        """Score every dimension, skipping scorers that report no evidence.

        The result is ordered by registration order; the returned list contains
        exactly the dimensions that could be scored, so callers know which
        dimensions were unavailable.
        """
        scores: list[DimensionScore] = []
        for scorer in self._scorers:
            result = scorer.score(inputs)
            if result is not None:
                scores.append(result)
        return scores


class AnalysisWithMetrics(Protocol):
    """An analyzer result that carries derived metrics."""

    @property
    def metrics(self) -> list[MetricRecord]: ...


def metric_value(result: AnalysisWithMetrics, metric_id: str) -> MetricValue:
    """Return a derived metric's value, or ``None`` when it is absent."""
    for record in result.metrics:
        if record.id == metric_id:
            return record.value
    return None


def metric_sources(result: AnalysisWithMetrics, *metric_ids: str) -> list[SourceReference]:
    """Deduplicated provenance of the requested metrics, preserving order."""
    seen: dict[tuple[SourceEntityKind, str, str | None], SourceReference] = {}
    for record in result.metrics:
        if record.id in metric_ids:
            for ref in record.sources:
                seen[(ref.entity, ref.identifier, ref.field)] = ref
    return list(seen.values())


def dedupe_sources(refs: list[SourceReference]) -> list[SourceReference]:
    """Deduplicate provenance references, preserving first-seen order."""
    seen: dict[tuple[SourceEntityKind, str, str | None], SourceReference] = {}
    for ref in refs:
        seen[(ref.entity, ref.identifier, ref.field)] = ref
    return list(seen.values())
