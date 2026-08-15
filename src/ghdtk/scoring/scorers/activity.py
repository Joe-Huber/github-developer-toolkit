"""Activity dimension scorer (issue #49).

Scores the ``activity`` dimension from the commit analysis (issue #37): the
volume and breadth of a developer's commit history
(:mod:`~ghdtk.analyzers.commits`).

Documented formula (blended, 0-100):

- **Volume** (weight 0.4): log-scaled total commits up to
  ``activity_volume_target``.
- **Cadence** (weight 0.3): commits per month, linear up to ``cadence_target``.
- **Breadth** (weight 0.3): active days in the coverage window, linear up to 90.

Empty-data handling: without the commit analysis the dimension cannot be scored
and ``None`` is returned; a coverage window with no commits scores zero on
every component.
"""

from __future__ import annotations

from ghdtk.models.derived import DimensionId, DimensionScore
from ghdtk.scoring.framework import ScoreInputs, metric_sources
from ghdtk.scoring.normalize import (
    ScoredComponent,
    blend,
    normalize_linear,
    normalize_log,
)
from ghdtk.scoring.scorers.base import BaseScorer

_ACTIVE_DAY_TARGET = 90


class ActivityScorer(BaseScorer):
    """Score commit volume, cadence and active-day breadth."""

    dimension = DimensionId.ACTIVITY
    label = "Activity"

    def score(self, inputs: ScoreInputs) -> DimensionScore | None:
        commits = inputs.commits
        if commits is None:
            return None
        cadence = commits.cadence_per_month or 0.0
        cadence_component = normalize_linear(cadence, 0.0, self.config.cadence_target)
        volume_component = normalize_log(
            float(commits.total_commits), 1.0, float(self.config.activity_volume_target)
        )
        breadth_component = normalize_linear(float(commits.active_days), 0.0, _ACTIVE_DAY_TARGET)
        components = [
            ScoredComponent(
                component_id="commit_volume",
                label="Commit volume",
                value=volume_component,
                weight=0.4,
                metric_id="commit_activity.total_commits",
                sources=tuple(metric_sources(commits, "commit_activity.total_commits")),
            ),
            ScoredComponent(
                component_id="commit_cadence",
                label="Commit cadence",
                value=cadence_component,
                weight=0.3,
                metric_id="commit_activity.cadence_per_month",
                sources=tuple(metric_sources(commits, "commit_activity.cadence_per_month")),
            ),
            ScoredComponent(
                component_id="active_days",
                label="Active-day breadth",
                value=breadth_component,
                weight=0.3,
                metric_id="commit_activity.active_days",
                sources=tuple(metric_sources(commits, "commit_activity.active_days")),
            ),
        ]
        score, breakdown = blend(components)
        rationale = (
            f"{commits.total_commits} commits, cadence {cadence:.1f}/month over "
            f"{commits.active_days} active days"
        )
        return self._result(score, rationale, breakdown)
