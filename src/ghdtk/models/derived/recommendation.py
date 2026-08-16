"""Derived recommendation model.

Actionable suggestions derived from findings and low scores, each referencing
the evidence and metrics that motivated it. Recommendations are produced from
templated rules, so every recommendation traces back to the rule (``template_id``)
and the finding(s) that triggered it (``finding_ids``).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ghdtk.models.derived.finding import FindingSeverity
from ghdtk.models.derived.provenance import SourceReference


class RecommendationPriority(StrEnum):
    """Priority of a recommendation."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationEffort(StrEnum):
    """Estimated effort of a recommendation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Recommendation(BaseModel):
    """One actionable recommendation."""

    model_config = ConfigDict(frozen=True)

    id: str
    priority: RecommendationPriority
    action: str
    rationale: str
    template_id: str = ""
    severity: FindingSeverity | None = None
    effort: RecommendationEffort = RecommendationEffort.MEDIUM
    finding_ids: list[str] = Field(default_factory=list)
    metric_ids: list[str] = Field(default_factory=list)
    sources: list[SourceReference] = Field(default_factory=list)
