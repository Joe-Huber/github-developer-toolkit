"""Derived metric model.

A single, named analysis result with its value, provenance, and confidence.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ghdtk.models.derived.provenance import SourceReference

MetricValue = int | float | bool | str | None


class MetricRecord(BaseModel):
    """One derived metric produced by an analyzer."""

    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    value: MetricValue
    sources: list[SourceReference] = Field(default_factory=list)
    timestamp: datetime
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
