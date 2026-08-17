"""Derived metric model.

A single, named analysis result with its value, provenance, confidence, and
availability (issue #64).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ghdtk.models.derived.provenance import SourceReference

MetricValue = int | float | bool | str | None


class MetricAvailability(StrEnum):
    """How reliably a metric is exposed by GitHub (issue #64).

    Every derived metric declares its availability so reports never claim a
    value GitHub does not reliably provide:

    - ``AVAILABLE`` — GitHub exposes the underlying data reliably; the value is
      the observed data point.
    - ``PARTIAL`` — GitHub exposes the data but only within a bounded window or
      coverage (e.g. commit/PR/issue totals collected within the request
      budget, not lifetime history); the value is real but reflects that
      coverage.
    - ``UNAVAILABLE`` — GitHub does not reliably provide the underlying data
      (e.g. historical follower counts, org membership count); the value is
      ``None`` and reports surface it as "unavailable"/"insufficient data".
    """

    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class MetricRecord(BaseModel):
    """One derived metric produced by an analyzer."""

    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    value: MetricValue
    sources: list[SourceReference] = Field(default_factory=list)
    timestamp: datetime
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    availability: MetricAvailability = MetricAvailability.AVAILABLE

    @property
    def is_unavailable(self) -> bool:
        """Whether this metric is typed as unsupported (value is ``None``)."""
        return self.availability == MetricAvailability.UNAVAILABLE


__all__ = ["MetricAvailability", "MetricRecord", "MetricValue"]
