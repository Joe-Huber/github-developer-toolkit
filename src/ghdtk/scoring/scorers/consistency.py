"""Consistency dimension scorer (issue #48).

Scores the ``consistency`` dimension from the commit & contribution analysis
(issue #37): how regularly a developer commits over time, using commit-gap
statistics (:mod:`~ghdtk.analyzers.commits`) and, when available, the
contribution calendar (:mod:`~ghdtk.analyzers.contribution_calendar`).

Documented formula (blended, 0-100):

- **Commit regularity** (weight 0.7): 50% cadence (commits/month, linear up to
  ``cadence_target``), 30% median-gap component (linear from ``gap_good_days``
  down to ``gap_bad_days``) and 20% active-day share (active days over the
  covered span).
- **Calendar regularity** (weight 0.3, when assessed): 50% calendar density,
  25% longest streak (linear up to 30 days) and 25% longest-gap component
  (linear from ``gap_good_days`` down to ``gap_bad_days``).

Empty-data handling: without the commit analysis the dimension cannot be scored
and ``None`` is returned; a coverage window with no commits scores zero on the
commit-regularity component. The calendar component is dropped (and remaining
weight re-normalized) when the calendar analysis was not run.
"""

from __future__ import annotations

from ghdtk.analyzers.commits import CommitActivity
from ghdtk.analyzers.contribution_calendar import ContributionCalendarAnalysis
from ghdtk.models.derived import DimensionId, DimensionScore
from ghdtk.scoring.framework import ScoreInputs, metric_sources
from ghdtk.scoring.normalize import (
    ScoredComponent,
    blend,
    normalize_linear,
    normalize_ratio,
)
from ghdtk.scoring.scorers.base import BaseScorer

_STREAK_TARGET = 30
_ACTIVE_DAY_TARGET = 90


class ConsistencyScorer(BaseScorer):
    """Score commit regularity and calendar-driven consistency."""

    dimension = DimensionId.CONSISTENCY
    label = "Consistency"

    def score(self, inputs: ScoreInputs) -> DimensionScore | None:
        commits = inputs.commits
        if commits is None:
            return None
        components = [self._commit_component(commits)]
        if inputs.contribution_calendar is not None:
            components.append(self._calendar_component(inputs.contribution_calendar))
        score, breakdown = blend(components)
        total_commits = commits.total_commits
        rationale = (
            f"Commit regularity across {total_commits} commits in the coverage "
            f"window; {len(components)} components blended"
        )
        return self._result(score, rationale, breakdown)

    def _gap_component(self, value: float | None) -> float:
        if value is None:
            return 100.0
        return normalize_linear(
            value,
            float(self.config.gap_good_days),
            float(self.config.gap_bad_days),
            high_is_good=False,
        )

    def _commit_component(self, commits: CommitActivity) -> ScoredComponent:
        cadence = commits.cadence_per_month
        median_gap = commits.median_gap_days
        span_days = commits.span_days
        active_days = commits.active_days

        if commits.total_commits == 0:
            value = 0.0
        else:
            cadence_component = (
                normalize_linear(cadence, 0.0, self.config.cadence_target)
                if cadence is not None
                else 0.0
            )
            gap_component = self._gap_component(median_gap)
            if span_days:
                active_share = normalize_ratio(active_days / span_days)
            else:
                active_share = normalize_linear(float(active_days), 0.0, _ACTIVE_DAY_TARGET)
            value = 0.50 * cadence_component + 0.30 * gap_component + 0.20 * active_share
        sources = metric_sources(
            commits,
            "commit_activity.total_commits",
            "commit_activity.cadence_per_month",
            "commit_activity.median_gap_days",
            "commit_activity.active_days",
        )
        return ScoredComponent(
            component_id="commit_regularity",
            label="Commit regularity",
            value=value,
            weight=0.7,
            metric_id="commit_activity.cadence_per_month",
            sources=tuple(sources),
        )

    def _calendar_component(self, calendar: ContributionCalendarAnalysis) -> ScoredComponent:
        total = calendar.total_contributions
        density = calendar.density
        longest_streak = calendar.longest_streak
        longest_gap = calendar.longest_gap_days

        if total is None or total == 0:
            value = 0.0
        else:
            density_component = normalize_ratio(density)
            streak_component = normalize_linear(float(longest_streak), 0.0, _STREAK_TARGET)
            gap_component = self._gap_component(
                float(longest_gap) if longest_gap is not None else None
            )
            value = 0.50 * density_component + 0.25 * streak_component + 0.25 * gap_component
        sources = metric_sources(
            calendar,
            "contribution_calendar.density",
            "contribution_calendar.longest_streak",
            "contribution_calendar.longest_gap_days",
        )
        return ScoredComponent(
            component_id="calendar_regularity",
            label="Calendar regularity",
            value=value,
            weight=0.3,
            metric_id="contribution_calendar.density",
            sources=tuple(sources),
        )
