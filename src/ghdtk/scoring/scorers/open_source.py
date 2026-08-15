"""Open-source dimension scorer (issue #49).

Scores the ``open_source`` dimension from the pull request analysis (issue
#40): how a developer contributes to open-source projects through pull
requests (:mod:`~ghdtk.analyzers.pull_requests`).

Documented formula (blended, 0-100):

- **Volume** (weight 0.3): log-scaled pull-request count up to
  ``pr_volume_target``.
- **Merge rate** (weight 0.3): the share of pull requests that were merged.
- **External share** (weight 0.2): the share of pull requests opened against
  repositories the profile does not own.
- **Collaboration** (weight 0.2): the share of pull requests that received
  review comments.

Empty-data handling: without the pull-request analysis the dimension cannot be
scored and ``None`` is returned; a profile with no pull requests scores zero.
"""

from __future__ import annotations

from ghdtk.models.derived import DimensionId, DimensionScore
from ghdtk.scoring.framework import ScoreInputs, metric_sources
from ghdtk.scoring.normalize import (
    ScoredComponent,
    blend,
    normalize_log,
    normalize_ratio,
)
from ghdtk.scoring.scorers.base import BaseScorer


class OpenSourceScorer(BaseScorer):
    """Score pull-request volume, acceptance and external collaboration."""

    dimension = DimensionId.OPEN_SOURCE
    label = "Open source"

    def score(self, inputs: ScoreInputs) -> DimensionScore | None:
        pull_requests = inputs.pull_requests
        if pull_requests is None:
            return None
        total = pull_requests.total_pull_requests
        merge_rate = pull_requests.merge_rate
        external_share = pull_requests.external_share
        reviewed_share = pull_requests.reviewed_share

        volume_component = normalize_log(float(total), 1.0, float(self.config.pr_volume_target))
        merge_component = normalize_ratio(float(merge_rate) if merge_rate is not None else 0.0)
        external_component = normalize_ratio(
            float(external_share) if external_share is not None else 0.0
        )
        reviewed_component = normalize_ratio(
            float(reviewed_share) if reviewed_share is not None else 0.0
        )

        components = [
            ScoredComponent(
                component_id="pull_request_volume",
                label="Pull-request volume",
                value=volume_component,
                weight=0.3,
                metric_id="pull_requests.total_pull_requests",
                sources=tuple(metric_sources(pull_requests, "pull_requests.total_pull_requests")),
            ),
            ScoredComponent(
                component_id="pull_request_merge_rate",
                label="Pull-request merge rate",
                value=merge_component,
                weight=0.3,
                metric_id="pull_requests.merge_rate",
                sources=tuple(metric_sources(pull_requests, "pull_requests.merge_rate")),
            ),
            ScoredComponent(
                component_id="external_engagement",
                label="External engagement",
                value=external_component,
                weight=0.2,
                metric_id="pull_requests.external_share",
                sources=tuple(metric_sources(pull_requests, "pull_requests.external_share")),
            ),
            ScoredComponent(
                component_id="pull_request_collaboration",
                label="Review collaboration",
                value=reviewed_component,
                weight=0.2,
                metric_id="pull_requests.reviewed_share",
                sources=tuple(metric_sources(pull_requests, "pull_requests.reviewed_share")),
            ),
        ]
        score, breakdown = blend(components)
        rationale = (
            f"{total} pull requests, merge rate {merge_component / 100:.2f}, "
            f"external share {external_component / 100:.2f}"
        )
        return self._result(score, rationale, breakdown)
