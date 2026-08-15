"""Contribution dimension scorer (issue #49).

Scores the ``contribution`` dimension from the contribution-calendar analysis
(issue #37): the total volume, density and streak behavior of a developer's
contributions (:mod:`~ghdtk.analyzers.contribution_calendar`).

Documented formula (blended, 0-100):

- **Volume** (weight 0.4): log-scaled total contributions up to
  ``contribution_volume_target``.
- **Density** (weight 0.35): the share of days with contributions in the
  covered window.
- **Streaks** (weight 0.25): 60% longest streak (linear up to 30 days) plus
  40% longest-gap component (linear from ``gap_good_days`` down to
  ``gap_bad_days``).

Empty-data handling: without the calendar analysis the dimension cannot be
scored and ``None`` is returned; a calendar with no contribution data scores
zero on every component.
"""

from __future__ import annotations

from ghdtk.models.derived import DimensionId, DimensionScore
from ghdtk.scoring.framework import ScoreInputs, metric_sources
from ghdtk.scoring.normalize import (
    ScoredComponent,
    blend,
    normalize_linear,
    normalize_log,
    normalize_ratio,
)
from ghdtk.scoring.scorers.base import BaseScorer

_STREAK_TARGET = 30


class ContributionScorer(BaseScorer):
    """Score contribution volume, density and streaks."""

    dimension = DimensionId.CONTRIBUTION
    label = "Contribution"

    def score(self, inputs: ScoreInputs) -> DimensionScore | None:
        calendar = inputs.contribution_calendar
        if calendar is None:
            return None
        total = calendar.total_contributions
        density = calendar.density
        longest_streak = calendar.longest_streak
        longest_gap = calendar.longest_gap_days

        volume_component = normalize_log(
            float(total or 0), 1.0, float(self.config.contribution_volume_target)
        )
        density_component = normalize_ratio(density)
        streak_component = normalize_linear(float(longest_streak), 0.0, _STREAK_TARGET)
        gap_component = (
            normalize_linear(
                float(longest_gap),
                float(self.config.gap_good_days),
                float(self.config.gap_bad_days),
                high_is_good=False,
            )
            if longest_gap is not None
            else 100.0
        )
        no_contribution_data = total is None or total == 0
        streak_blend = (
            0.0 if no_contribution_data else 0.60 * streak_component + 0.40 * gap_component
        )

        components = [
            ScoredComponent(
                component_id="contribution_volume",
                label="Contribution volume",
                value=volume_component,
                weight=0.4,
                metric_id="contribution_calendar.total_contributions",
                sources=tuple(
                    metric_sources(calendar, "contribution_calendar.total_contributions")
                ),
            ),
            ScoredComponent(
                component_id="contribution_density",
                label="Contribution density",
                value=density_component,
                weight=0.35,
                metric_id="contribution_calendar.density",
                sources=tuple(metric_sources(calendar, "contribution_calendar.density")),
            ),
            ScoredComponent(
                component_id="contribution_streaks",
                label="Streaks and gaps",
                value=streak_blend,
                weight=0.25,
                metric_id="contribution_calendar.longest_streak",
                sources=tuple(
                    metric_sources(
                        calendar,
                        "contribution_calendar.longest_streak",
                        "contribution_calendar.longest_gap_days",
                    )
                ),
            ),
        ]
        score, breakdown = blend(components)
        rationale = (
            f"{int(total or 0)} contributions, density {density:.2f}, "
            f"longest streak {longest_streak} days"
        )
        return self._result(score, rationale, breakdown)
