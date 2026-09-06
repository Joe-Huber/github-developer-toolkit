"""Community dimension scorer (issue #49).

Scores the ``engagement`` dimension from the follower/network analysis (issue
#35): the size, balance and reach of a developer's follower network
(:mod:`~ghdtk.analyzers.network`).

Documented formula (blended, 0-100):

- **Audience** (weight 0.4): log-scaled follower count up to
  ``follower_volume_target``.
- **Balance** (weight 0.3): follower/following ratio with full credit for the
  healthy band between ``0.5`` and ``5.0`` (covering both audience-driven
  profiles with more followers than following and network-driven profiles
  leaning the other way), a linear taper below ``0.5``, and a logarithmic
  taper above ``5.0`` so popular profiles with large audiences are not
  disproportionately punished. When the ratio was not recorded, it is derived
  from the raw counts.
- **Reach** (weight 0.3): log-scaled reach estimate up to five times
  ``follower_volume_target``.

Empty-data handling: without follower data the dimension cannot be scored and
``None`` is returned; a profile with zero followers scores zero.
"""

from __future__ import annotations

import math

from ghdtk.models.derived import DimensionId, DimensionScore
from ghdtk.scoring.framework import (
    ScoreInputs,
    metric_sources,
)
from ghdtk.scoring.normalize import (
    ScoredComponent,
    blend,
    clamp,
    normalize_log,
)
from ghdtk.scoring.scorers.base import BaseScorer


class CommunityScorer(BaseScorer):
    """Score follower audience, balance and reach."""

    dimension = DimensionId.ENGAGEMENT
    label = "Community"

    @staticmethod
    def _balance_score(ratio: float) -> float:
        """Score follower/following balance with a generous healthy band.

        Full credit (100) when the ratio is in the band [0.5, 5.0], covering
        audience-driven profiles with more followers than following *and*
        network-driven profiles with the reverse.  Below 0.5 a linear taper
        reaches zero at ratio == 0.  Above 5.0 a logarithmic taper falls
        slowly (e.g. ratio 20 → ~62, ratio 100 → ~43) so popular profiles
        with very large audiences are not penalized as harshly as before.
        """
        if ratio <= 0:
            return 0.0
        if ratio < 0.5:
            return clamp(ratio / 0.5 * 100.0, 0.0, 100.0)
        if ratio <= 5.0:
            return 100.0
        decades = math.log10(ratio / 5.0)
        return clamp(100.0 / (1.0 + decades), 0.0, 100.0)

    def score(self, inputs: ScoreInputs) -> DimensionScore | None:
        network = inputs.network
        if network is None:
            return None
        followers = network.followers_count
        if followers is None:
            return None
        following = network.following_count
        ratio = network.ratio
        reach = network.reach_estimate

        audience_component = normalize_log(
            float(followers), 1.0, float(self.config.follower_volume_target)
        )
        if ratio is None:
            if following and following > 0 and followers:
                ratio = followers / following
            elif followers > 0:
                ratio = float("inf")
            else:
                ratio = 0.0

        balance_component = self._balance_score(ratio)
        reach_component = normalize_log(
            float(reach), 1.0, float(self.config.follower_volume_target) * 5
        )

        components = [
            ScoredComponent(
                component_id="follower_audience",
                label="Follower audience",
                value=audience_component,
                weight=0.4,
                metric_id="network.followers.count",
                sources=tuple(metric_sources(network, "network.followers.count")),
            ),
            ScoredComponent(
                component_id="follower_balance",
                label="Follower balance",
                value=balance_component,
                weight=0.3,
                metric_id="network.followers.ratio",
                sources=tuple(
                    metric_sources(
                        network,
                        "network.followers.ratio",
                        "network.followers.count",
                        "network.following.count",
                    )
                ),
            ),
            ScoredComponent(
                component_id="network_reach",
                label="Network reach",
                value=reach_component,
                weight=0.3,
                metric_id="network.followers.reach",
                sources=tuple(metric_sources(network, "network.followers.reach")),
            ),
        ]
        score, breakdown = blend(components)
        ratio_desc = ">100" if ratio == float("inf") else f"{ratio:.2f}"
        rationale = (
            f"{followers} followers / {following} following (ratio {ratio_desc}), reach {reach:.0f}"
        )
        return self._result(score, rationale, breakdown)
