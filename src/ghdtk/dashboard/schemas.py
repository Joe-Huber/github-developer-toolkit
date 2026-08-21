"""API response schemas for the dashboard.

Thin wrappers around the core :class:`~ghdtk.models.derived.analysis.Report`
model so the API has a stable, documented contract independent of internal
model changes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from ghdtk.models.derived.analysis import Report


class ReportResponse(BaseModel):
    """Top-level API response wrapping a full analysis report."""

    tool_version: str
    generated_at: datetime
    profile: dict[str, Any]

    @classmethod
    def from_report(cls, report: Report) -> ReportResponse:
        return cls(
            tool_version=report.tool_version,
            generated_at=report.generated_at,
            profile=report.profile.model_dump(mode="json"),
        )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
