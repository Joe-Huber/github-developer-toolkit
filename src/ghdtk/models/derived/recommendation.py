"""Derived recommendation model.

Actionable suggestions derived from findings, each referencing the evidence
and metrics that motivated it.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ghdtk.models.derived.provenance import SourceReference


class RecommendationPriority(StrEnum):
    """Priority of a recommendation."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Recommendation(BaseModel):
    """One actionable recommendation."""

    model_config = ConfigDict(frozen=True)

    id: str
    priority: RecommendationPriority
    action: str
    rationale: str
    finding_ids: list[str] = Field(default_factory=list)
    metric_ids: list[str] = Field(default_factory=list)
    sources: list[SourceReference] = Field(default_factory=list)
