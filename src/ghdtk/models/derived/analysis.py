"""Derived analysis container and report DTO.

``ProfileAnalysis`` is the snapshot container for a complete analysis of one
profile; ``Report`` is the final serializable DTO produced for display or
export.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ghdtk import __version__
from ghdtk.models.derived.finding import Finding
from ghdtk.models.derived.metric import MetricRecord
from ghdtk.models.derived.recommendation import Recommendation
from ghdtk.models.derived.score import DimensionScore, OverallScore


class ProfileAnalysis(BaseModel):
    """Snapshot container for the analysis of one GitHub profile."""

    model_config = ConfigDict(frozen=True)

    username: str
    analyzed_at: datetime
    schema_version: int = 1
    metrics: list[MetricRecord] = Field(default_factory=list)
    scores: list[DimensionScore] = Field(default_factory=list)
    overall: OverallScore | None = None
    findings: list[Finding] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)


class Report(BaseModel):
    """Report DTO — the complete, serializable analysis output."""

    model_config = ConfigDict(frozen=True)

    tool_version: str = __version__
    generated_at: datetime
    profile: ProfileAnalysis
