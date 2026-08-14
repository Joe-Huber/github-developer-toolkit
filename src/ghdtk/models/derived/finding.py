"""Derived finding model.

Findings surface issues or opportunities in a profile, backed by raw
evidence and references to the recommendations that address them.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ghdtk.models.derived.provenance import SourceReference
from ghdtk.models.derived.score import DimensionId


class FindingSeverity(StrEnum):
    """Severity of a finding."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Finding(BaseModel):
    """One analysis finding about a profile."""

    model_config = ConfigDict(frozen=True)

    id: str
    type: str
    severity: FindingSeverity
    title: str
    message: str
    dimension: DimensionId | None = None
    evidence: list[SourceReference] = Field(default_factory=list)
    recommendation_ids: list[str] = Field(default_factory=list)
