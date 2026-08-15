"""Repository dimension scorer (issue #48).

Scores the ``code_quality`` dimension from the repository analysis (issue
#27): repository metadata quality (:mod:`~ghdtk.analyzers.repository_quality`),
repository activity (:mod:`~ghdtk.analyzers.repository_activity`) and
portfolio composition (:mod:`~ghdtk.analyzers.portfolio`).

Documented formula (blended, 0-100):

- **Repository quality** (weight 1.0): 30% description coverage, 30% README
  coverage, 15% license coverage, 10% homepage coverage and 15% topics
  component (linear up to an average of 5 topics per repository).
- **Repository activity** (weight 0.5, when assessed): 50% share of active
  repositories plus 50% staleness component (median staleness in days, inverted
  against a 90-day horizon).
- **Portfolio composition** (weight 0.25, when assessed): 60% standout count
  (linear up to 3 standouts) plus 40% log-scaled total stars.

Empty-data handling: without the repository-quality analysis the dimension
cannot be scored and ``None`` is returned; a profile with no repositories
scores zero on the quality component with an explanatory rationale. The
activity and portfolio components are dropped (and remaining weight
re-normalized) when their analyses were not run.
"""

from __future__ import annotations

from ghdtk.analyzers.portfolio import PortfolioComposition
from ghdtk.analyzers.repository_activity import RepositoryActivity
from ghdtk.analyzers.repository_quality import RepositoryQuality
from ghdtk.models.derived import DimensionId, DimensionScore
from ghdtk.scoring.framework import (
    ScoreInputs,
    metric_sources,
    metric_value,
)
from ghdtk.scoring.normalize import (
    ScoredComponent,
    blend,
    normalize_linear,
    normalize_log,
    normalize_ratio,
)
from ghdtk.scoring.scorers.base import BaseScorer

_STALE_DAYS = 90
_TOPICS_TARGET = 5
_STANDOUT_TARGET = 3


class RepositoryScorer(BaseScorer):
    """Score repository quality, activity and portfolio composition."""

    dimension = DimensionId.CODE_QUALITY
    label = "Code quality"

    def score(self, inputs: ScoreInputs) -> DimensionScore | None:
        quality = inputs.repository_quality
        if quality is None:
            return None
        components = [self._quality_component(quality)]
        if inputs.repository_activity is not None:
            components.append(self._activity_component(inputs.repository_activity))
        if inputs.portfolio is not None:
            components.append(self._portfolio_component(inputs.portfolio))
        score, breakdown = blend(components)
        total = len(quality.signals)
        rationale = (
            f"Repository quality across {total} repositories with "
            f"{len(components)} components blended"
        )
        return self._result(score, rationale, breakdown)

    def _quality_component(self, quality: RepositoryQuality) -> ScoredComponent:
        description = float(metric_value(quality, "portfolio.quality.description_coverage") or 0)
        readme = float(metric_value(quality, "portfolio.quality.readme_coverage") or 0)
        license_ = float(metric_value(quality, "portfolio.quality.license_coverage") or 0)
        homepage = float(metric_value(quality, "portfolio.quality.homepage_coverage") or 0)
        topics = float(metric_value(quality, "portfolio.quality.topics.average") or 0)

        value = (
            0.30 * normalize_ratio(description)
            + 0.30 * normalize_ratio(readme)
            + 0.15 * normalize_ratio(license_)
            + 0.10 * normalize_ratio(homepage)
            + 0.15 * normalize_linear(topics, 0.0, _TOPICS_TARGET)
        )
        sources = metric_sources(
            quality,
            "portfolio.quality.description_coverage",
            "portfolio.quality.readme_coverage",
            "portfolio.quality.license_coverage",
            "portfolio.quality.homepage_coverage",
            "portfolio.quality.topics.average",
        )
        return ScoredComponent(
            component_id="repository_quality",
            label="Repository quality",
            value=value,
            weight=1.0,
            metric_id="portfolio.quality.description_coverage",
            sources=tuple(sources),
        )

    def _activity_component(self, activity: RepositoryActivity) -> ScoredComponent:
        total = int(metric_value(activity, "portfolio.activity.repos.total") or 0)
        active = int(metric_value(activity, "portfolio.activity.repos.active") or 0)
        median_staleness = metric_value(activity, "portfolio.activity.median_staleness_days")
        if total == 0:
            value = 0.0
        else:
            active_share = normalize_ratio(active / total)
            staleness = (
                normalize_linear(float(median_staleness), 0.0, _STALE_DAYS, high_is_good=False)
                if median_staleness is not None
                else 0.0
            )
            value = 0.50 * active_share + 0.50 * staleness
        sources = metric_sources(
            activity,
            "portfolio.activity.repos.total",
            "portfolio.activity.repos.active",
            "portfolio.activity.median_staleness_days",
        )
        return ScoredComponent(
            component_id="repository_activity",
            label="Repository activity",
            value=value,
            weight=0.5,
            metric_id="portfolio.activity.repos.active",
            sources=tuple(sources),
        )

    def _portfolio_component(self, portfolio: PortfolioComposition) -> ScoredComponent:
        standout_count = len(portfolio.standouts)
        total_stars = int(metric_value(portfolio, "portfolio.composition.total_stars") or 0)
        standout_component = normalize_linear(float(standout_count), 0.0, _STANDOUT_TARGET)
        stars_component = normalize_log(
            float(total_stars), 1.0, float(self.config.star_volume_target)
        )
        value = 0.60 * standout_component + 0.40 * stars_component
        sources = metric_sources(portfolio, "portfolio.composition.total_stars")
        return ScoredComponent(
            component_id="portfolio_composition",
            label="Portfolio composition",
            value=value,
            weight=0.25,
            metric_id="portfolio.composition.total_stars",
            sources=tuple(sources),
        )
