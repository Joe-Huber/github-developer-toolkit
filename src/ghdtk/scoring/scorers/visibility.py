"""Visibility dimension scorer (issue #49).

Scores the ``visibility`` dimension from the stars and language analyses
(issue #32 and #43): how discoverable a developer's portfolio is through
aggregated stars (:mod:`~ghdtk.analyzers.stars`) and its language mix
(:mod:`~ghdtk.analyzers.languages`).

Documented formula (blended, 0-100):

- **Stars** (weight 0.6, or 1.0 when languages were not assessed): log-scaled
  total portfolio stars up to ``star_volume_target``.
- **Languages** (weight 0.4, when assessed): 60% distinct-language count
  (linear up to 8) plus 40% byte-coverage (share of repositories with usable
  byte statistics).

Empty-data handling: without the stars analysis the dimension cannot be scored
and ``None`` is returned; a portfolio with no stars scores zero on the stars
component. The languages component is dropped (and remaining weight
re-normalized) when the language analysis was not run or reported no data.
"""

from __future__ import annotations

from ghdtk.analyzers.languages import LanguageDistributionAnalysis
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

_LANGUAGES_TARGET = 8


class VisibilityScorer(BaseScorer):
    """Score portfolio stars and language discoverability."""

    dimension = DimensionId.VISIBILITY
    label = "Visibility"

    def score(self, inputs: ScoreInputs) -> DimensionScore | None:
        stars = inputs.stars
        if stars is None:
            return None
        total_stars = metric_value(stars, "portfolio.stars.total")
        if total_stars is None:
            total_stars = sum(entry.stars for entry in stars.ranking)
        stars_component = normalize_log(
            float(total_stars), 1.0, float(self.config.star_volume_target)
        )
        components = [
            ScoredComponent(
                component_id="portfolio_stars",
                label="Portfolio stars",
                value=stars_component,
                weight=0.6,
                metric_id="portfolio.stars.total",
                sources=tuple(metric_sources(stars, "portfolio.stars.total")),
            )
        ]
        if inputs.languages is not None:
            components.append(self._languages_component(inputs.languages))
        score, breakdown = blend(components)
        rationale = f"{int(total_stars)} total stars; {len(components)} components blended"
        return self._result(score, rationale, breakdown)

    def _languages_component(self, languages: LanguageDistributionAnalysis) -> ScoredComponent:
        distinct = languages.distinct_languages
        with_stats = languages.repos_with_stats
        total = (
            languages.repos_with_stats
            + languages.declared_only_count
            + languages.unknown_count
            + languages.empty_count
        )

        distinct_component = normalize_linear(float(distinct), 0.0, _LANGUAGES_TARGET)
        coverage_component = normalize_ratio(with_stats / total if total else 0.0)
        value = 0.60 * distinct_component + 0.40 * coverage_component
        sources = metric_sources(
            languages,
            "languages.distinct_languages",
            "languages.repos.with_byte_stats",
            "languages.repos.total",
        )
        return ScoredComponent(
            component_id="language_mix",
            label="Language diversity",
            value=value,
            weight=0.4,
            metric_id="languages.distinct_languages",
            sources=tuple(sources),
        )
