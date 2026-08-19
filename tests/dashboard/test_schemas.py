"""Tests for dashboard API schemas (issue #94)."""

from __future__ import annotations

from datetime import UTC, datetime

from ghdtk.dashboard.schemas import HealthResponse, ReportResponse
from ghdtk.models.derived.analysis import ProfileAnalysis, Report


def test_health_response_default() -> None:
    h = HealthResponse()
    assert h.status == "ok"


def test_report_response_from_report() -> None:
    profile = ProfileAnalysis(
        username="testuser",
        analyzed_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    report = Report(
        generated_at=datetime(2025, 1, 1, tzinfo=UTC),
        profile=profile,
    )
    resp = ReportResponse.from_report(report)
    assert resp.tool_version == report.tool_version
    assert resp.generated_at == report.generated_at
    assert resp.profile["username"] == "testuser"
