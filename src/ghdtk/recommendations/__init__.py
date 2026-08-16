"""Recommendation engine.

Turns findings and low scores into actionable, prioritized, evidence-backed
recommendations (issues #51-#53).

Implemented layers:

- :mod:`~ghdtk.recommendations.rules` — the evidence-backed rule library that
  maps every finding to a recommendation, a disclosure or a positive standout
  (issue #52).
- :mod:`~ghdtk.recommendations.engine` — the :class:`RecommendationEngine`
  that turns findings and low scores into recommendations with evidence
  (issue #52).
- :mod:`~ghdtk.recommendations.synthesis` — :func:`synthesize`, which
  assembles strengths, weaknesses, red flags and a prioritized plan (issue
  #53).
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
from ghdtk.recommendations.synthesis import synthesize

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
    "synthesize",
]
