"""Derived scoring models.

Dimension scores summarize metrics into an explainable 0-100 score with a
transparent breakdown of how each component contributed.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ghdtk.models.derived.provenance import SourceReference


class DimensionId(StrEnum):
    """The profile dimensions a developer is scored on.

    ``DOCUMENTATION`` is retained so profile-README findings can reference a
    dimension; it is covered by the ``presence`` score rather than scored on
    its own.
    """

    PRESENCE = "presence"
    CODE_QUALITY = "code_quality"
    ACTIVITY = "activity"
    ENGAGEMENT = "engagement"
    DOCUMENTATION = "documentation"
    OPEN_SOURCE = "open_source"
    CONSISTENCY = "consistency"
    CONTRIBUTION = "contribution"
    VISIBILITY = "visibility"


class ScoreBreakdown(BaseModel):
    """One weighted component of a dimension score."""

    model_config = ConfigDict(frozen=True)

    component_id: str
    label: str
    weight: float = Field(ge=0.0)
    contribution: float = Field(ge=0.0)
    metric_id: str | None = None
    sources: list[SourceReference] = Field(default_factory=list)


class DimensionScore(BaseModel):
    """The score for one dimension of a profile."""

    model_config = ConfigDict(frozen=True)

    dimension: DimensionId
    score: float = Field(ge=0.0, le=100.0)
    weight: float = Field(ge=0.0)
    rationale: str | None = None
    breakdown: list[ScoreBreakdown] = Field(default_factory=list)


class DimensionContribution(BaseModel):
    """One dimension's contribution to the overall profile score."""

    model_config = ConfigDict(frozen=True)

    dimension: DimensionId
    score: float = Field(ge=0.0, le=100.0)
    weight: float = Field(ge=0.0)
    contribution: float = Field(ge=0.0, le=100.0)


class OverallScore(BaseModel):
    """The weighted overall profile score and its explainability output."""

    model_config = ConfigDict(frozen=True)

    overall: float = Field(ge=0.0, le=100.0)
    contributions: list[DimensionContribution] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
