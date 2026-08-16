"""End-to-end pipeline replay tests (issue #61).

Replays every recorded corpus session through the full pipeline —
``collect_profile`` → ``collect_profile_readme`` → ``ReportAssembler.assemble``
→ ``render_markdown`` / ``render_json`` / ``render_html`` — against strict
replay. The strict transport is the contract: any request outside the recorded
session raises, so the corpus must stay complete as the pipeline evolves, and
the rendered outputs must stay deterministic for a fixed snapshot and clock.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from replay import client_from_session, list_profiles, load_session

from ghdtk.collectors.collectors import collect_profile_readme
from ghdtk.collectors.orchestrator import collect_profile
from ghdtk.models.derived import Report
from ghdtk.models.raw import ProfileReadme, ProfileReadmeStatus, ProfileSnapshot
from ghdtk.report import (
    ReportAssembler,
    render_html,
    render_json,
    render_markdown,
    write_html,
    write_json,
    write_markdown,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

_README_PROFILES = {"active-developer", "popular-maintainer", "hidden-activity"}


def _collect_assembled(profile_id: str) -> tuple[ProfileSnapshot, ProfileReadme, Report]:
    """Run the recorded pipeline for ``profile_id`` and return the artifacts."""
    session = load_session(profile_id)
    username = session["profile"]["username"]
    client = client_from_session(session)
    snapshot = collect_profile(client, username, now=NOW)
    assert client.requests_made == len(session["requests"])
    readme = collect_profile_readme(client, username, repositories=snapshot.repositories)
    report = ReportAssembler().assemble(
        username=username, snapshot=snapshot, now=NOW, profile_readme=readme
    )
    return snapshot, readme, report


@pytest.mark.parametrize("profile_id", list_profiles())
def test_pipeline_collects_and_assembles_every_profile(profile_id: str) -> None:
    snapshot, readme, report = _collect_assembled(profile_id)

    assert snapshot.username == report.profile.username
    for record in snapshot.collections:
        assert record.status.value != "failed", record

    assert readme.username == snapshot.username
    if profile_id in _README_PROFILES:
        assert readme.status in (ProfileReadmeStatus.PRESENT, ProfileReadmeStatus.EMPTY)
    else:
        assert readme.status == ProfileReadmeStatus.NO_PROFILE_REPO

    assert report.profile.analyses is not None
    assert report.profile.overall is not None
    assert report.profile.synthesis is not None
    assert report.profile.metrics
    assert report.generated_at == NOW


@pytest.mark.parametrize("profile_id", list_profiles())
def test_report_is_deterministic_for_every_profile(profile_id: str) -> None:
    _, _, first = _collect_assembled(profile_id)
    _, _, second = _collect_assembled(profile_id)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


@pytest.mark.parametrize("profile_id", list_profiles())
def test_markdown_renders_deterministically_for_every_profile(profile_id: str) -> None:
    session = load_session(profile_id)
    username = session["profile"]["username"]
    _, _, report = _collect_assembled(profile_id)

    markdown = render_markdown(report)
    assert markdown.startswith(f"# GitHub Profile Report: {username}")
    assert username in markdown
    assert markdown.endswith("\n")
    assert render_markdown(report) == markdown


@pytest.mark.parametrize("profile_id", list_profiles())
def test_json_round_trips_for_every_profile(profile_id: str) -> None:
    session = load_session(profile_id)
    username = session["profile"]["username"]
    _, _, report = _collect_assembled(profile_id)

    rendered = render_json(report)
    payload: dict[str, Any] = json.loads(rendered)
    assert payload["profile"]["username"] == username
    assert payload["profile"]["overall"] is not None
    assert render_json(report) == rendered


@pytest.mark.parametrize("profile_id", list_profiles())
def test_html_renders_deterministically_for_every_profile(profile_id: str) -> None:
    _, _, report = _collect_assembled(profile_id)

    html = render_html(report)
    assert "<html" in html
    assert "GitHub Profile Report" in html
    assert render_html(report) == html


def test_write_helpers_persist_all_formats(tmp_path: Any) -> None:
    _, _, report = _collect_assembled("active-developer")

    md_path = write_markdown(report, tmp_path / "report.md")
    json_path = write_json(report, tmp_path / "report.json")
    html_path = write_html(report, tmp_path / "report.html")

    assert md_path.read_text(encoding="utf-8") == render_markdown(report)
    assert json_path.read_text(encoding="utf-8") == render_json(report)
    assert html_path.read_text(encoding="utf-8") == render_html(report)
    assert md_path.exists() and json_path.exists() and html_path.exists()


def test_reports_differ_across_profiles() -> None:
    rendered = {
        profile_id: render_markdown(_collect_assembled(profile_id)[2])
        for profile_id in list_profiles()
    }
    assert len(set(rendered.values())) == len(rendered)
