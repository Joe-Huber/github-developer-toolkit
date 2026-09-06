"""End-to-end dashboard integration tests (issue #194).

Connects the full pipeline — recorded corpus snapshot → ``ReportAssembler`` →
FastAPI ``/api/report/{username}`` → frontend TypeScript schema — so a mismatch
between what ``ghdtk analyze`` produces, what the dashboard serves, and what
``dashboard-ui/src/types/report.ts`` declares fails loudly in CI.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from replay import client_from_session, list_profiles, load_session

from ghdtk.collectors.collectors import collect_profile_readme
from ghdtk.collectors.orchestrator import collect_profile
from ghdtk.dashboard.app import create_app
from ghdtk.dashboard.schemas import ReportResponse
from ghdtk.models.derived import Report
from ghdtk.report import ReportAssembler, render_json

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

DIMENSION_IDS = frozenset(
    {
        "presence",
        "code_quality",
        "activity",
        "engagement",
        "documentation",
        "open_source",
        "consistency",
        "contribution",
        "visibility",
    }
)
FINDING_SEVERITIES = frozenset({"info", "low", "medium", "high", "critical"})
RECOMMENDATION_PRIORITIES = frozenset({"high", "medium", "low"})
METRIC_AVAILABILITIES = frozenset({"available", "partial", "unavailable"})
ANALYSIS_KEYS = frozenset(
    {
        "presence",
        "readme",
        "repository_quality",
        "repository_activity",
        "portfolio",
        "stars",
        "star_growth",
        "network",
        "commits",
        "contribution_calendar",
        "pull_requests",
        "issues",
        "languages",
        "technology",
    }
)


def _collect_session(
    profile_id: str,
) -> tuple[Any, Any, Report]:
    """Run the recorded pipeline; return snapshot, readme, and assembled report."""
    session = load_session(profile_id)
    username = session["profile"]["username"]
    client = client_from_session(session)
    snapshot = collect_profile(client, username, now=NOW)
    readme = collect_profile_readme(client, username, repositories=snapshot.repositories)
    report = ReportAssembler().assemble(
        username=username, snapshot=snapshot, now=NOW, profile_readme=readme
    )
    return snapshot, readme, report


def _assert_source_reference(item: dict[str, Any]) -> None:
    assert "entity" in item and isinstance(item["entity"], str)
    assert "identifier" in item and isinstance(item["identifier"], str)
    assert "field" in item and (item["field"] is None or isinstance(item["field"], str))


def _assert_metric(metric: dict[str, Any]) -> None:
    assert metric["id"], metric
    assert metric["label"], metric
    assert isinstance(metric["value"], (int, float, str, bool)) or metric["value"] is None
    assert isinstance(metric["timestamp"], str)
    assert isinstance(metric["confidence"], (int, float))
    assert metric["availability"] in METRIC_AVAILABILITIES
    assert isinstance(metric["sources"], list)
    for source in metric["sources"]:
        _assert_source_reference(source)


def _assert_finding(finding: dict[str, Any]) -> None:
    assert finding["id"] and finding["type"]
    assert isinstance(finding["title"], str) and isinstance(finding["message"], str)
    assert finding["severity"] in FINDING_SEVERITIES
    assert finding["dimension"] is None or finding["dimension"] in DIMENSION_IDS
    assert isinstance(finding["recommendation_ids"], list)
    for source in finding["evidence"]:
        _assert_source_reference(source)


def _assert_recommendation(rec: dict[str, Any]) -> None:
    assert rec["id"] and rec["template_id"]
    assert isinstance(rec["action"], str) and isinstance(rec["rationale"], str)
    assert rec["priority"] in RECOMMENDATION_PRIORITIES
    assert rec["severity"] is None or rec["severity"] in FINDING_SEVERITIES
    assert rec["effort"] in RECOMMENDATION_PRIORITIES
    assert isinstance(rec["finding_ids"], list) and isinstance(rec["metric_ids"], list)
    for source in rec["sources"]:
        _assert_source_reference(source)


def _assert_ts_profile_shape(profile: dict[str, Any]) -> None:
    """Validate the serialized profile against ``dashboard-ui/src/types/report.ts``."""
    assert isinstance(profile["username"], str)
    assert isinstance(profile["analyzed_at"], str)
    assert isinstance(profile["schema_version"], int)
    assert isinstance(profile["metrics"], list)
    for metric in profile["metrics"]:
        _assert_metric(metric)

    assert isinstance(profile["scores"], list)
    for score in profile["scores"]:
        assert score["dimension"] in DIMENSION_IDS
        assert isinstance(score["score"], (int, float))
        assert isinstance(score["weight"], (int, float))
        assert score["rationale"] is None or isinstance(score["rationale"], str)
        for item in score["breakdown"]:
            assert isinstance(item["component_id"], str)
            assert isinstance(item["label"], str)
            assert isinstance(item["weight"], (int, float))
            assert isinstance(item["contribution"], (int, float))
            assert item["metric_id"] is None or isinstance(item["metric_id"], str)
            for source in item["sources"]:
                _assert_source_reference(source)

    overall = profile["overall"]
    if overall is not None:
        assert isinstance(overall["overall"], (int, float))
        assert isinstance(overall["strengths"], list) and isinstance(overall["weaknesses"], list)
        for item in overall["contributions"]:
            assert item["dimension"] in DIMENSION_IDS
            assert isinstance(item["score"], (int, float))
            assert isinstance(item["weight"], (int, float))
            assert isinstance(item["contribution"], (int, float))

    for finding in profile["findings"]:
        _assert_finding(finding)
    for rec in profile["recommendations"]:
        _assert_recommendation(rec)

    synthesis = profile["synthesis"]
    if synthesis is not None:
        for key in ("strengths", "weaknesses", "red_flags"):
            assert isinstance(synthesis[key], list), key
        for rec in synthesis["plan"]:
            _assert_recommendation(rec)

    analyses = profile["analyses"]
    if analyses is not None:
        assert set(analyses) == ANALYSIS_KEYS
        for analysis in analyses.values():
            assert analysis is None or (
                isinstance(analysis["metrics"], list) and isinstance(analysis["findings"], list)
            )
        languages = analyses["languages"]
        if languages is not None:
            assert isinstance(languages["distinct_languages"], int)
            assert isinstance(languages["total_bytes"], (int, float))
            assert languages["dominant_language"] is None or isinstance(
                languages["dominant_language"], str
            )
            assert languages["dominant_share"] is None or isinstance(
                languages["dominant_share"], (int, float)
            )
            for entry in languages["distribution"]:
                assert isinstance(entry["language"], str)
                assert isinstance(entry["bytes"], (int, float))
                assert isinstance(entry["share"], (int, float))


@pytest.mark.parametrize("profile_id", list_profiles())
def test_analyze_json_matches_dashboard_response_schema(profile_id: str) -> None:
    """CLI ``analyze --format json`` output is identical to the dashboard schema."""
    report = _collect_session(profile_id)[2]
    response = ReportResponse.from_report(report)
    payload = response.model_dump(mode="json")
    assert payload == json.loads(render_json(report))


@pytest.mark.parametrize("profile_id", list_profiles())
def test_report_served_by_dashboard_matches_frontend_types(
    profile_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The endpoint serves a valid ReportResponse ingestible by the frontend."""
    snapshot, _, report = _collect_session(profile_id)
    username = report.profile.username

    def fake_collect(api_client: Any, username_: str, **_: Any) -> Any:
        assert username_ == username
        return snapshot

    def fake_collect_readme(api_client: Any, username_: str, **_: Any) -> None:
        return None

    monkeypatch.setattr("ghdtk.collectors.orchestrator.collect_profile", fake_collect)
    monkeypatch.setattr("ghdtk.collectors.collectors.collect_profile_readme", fake_collect_readme)

    client = TestClient(create_app())
    resp = client.get(f"/api/report/{username}")
    assert resp.status_code == 200

    payload = ReportResponse.model_validate(resp.json())
    assert payload.tool_version == report.tool_version
    _assert_ts_profile_shape(payload.model_dump(mode="json")["profile"])
