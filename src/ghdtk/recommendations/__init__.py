"""Recommendation engine.

Turns findings into actionable, prioritized, evidence-backed recommendations,
each referencing the evidence and metrics that motivated it.

Implemented layers:

- :mod:`~ghdtk.recommendations.rules` — the evidence-backed rule library that
  maps every finding to a recommendation, a disclosure or a positive standout
  (issue #52).
- :mod:`~ghdtk.recommendations.engine` — the :class:`RecommendationEngine`
  that turns findings and low scores into recommendations with evidence
  (issue #52).
"""

from __future__ import annotations

from ghdtk.recommendations.engine import (
    RecommendationEngine,
    backfill_finding_links,
    order_key,
)
from ghdtk.recommendations.rules import (
    DEFAULT_RULES,
    DISCLOSURE_PREFIXES,
    POSITIVE_PREFIXES,
    RecommendationRule,
    classify,
    extract_value,
    match_rule,
)

__all__ = [
    "DEFAULT_RULES",
    "DISCLOSURE_PREFIXES",
    "POSITIVE_PREFIXES",
    "RecommendationEngine",
    "RecommendationRule",
    "backfill_finding_links",
    "classify",
    "extract_value",
    "match_rule",
    "order_key",
]
