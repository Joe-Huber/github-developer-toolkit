"""Unit tests for the JSON report renderer (issue #56).

Verifies that ``render_json`` serializes the report DTO losslessly (matching
the DTO schema), that pretty and compact output behave as documented, that
``ensure_ascii`` keeps non-ASCII content readable, and that ``write_json``
writes the serialized document to a path.
"""

from __future__ import annotations

import json
from pathlib import Path

from _report_fixtures import _profile_readme, _rich_report, _rich_snapshot, _user

from ghdtk.report import ReportAssembler, render_json, write_json


def test_json_round_trips_losslessly() -> None:
    report = _rich_report()
    loaded = report.__class__.model_validate_json(render_json(report))
    assert loaded == report


def test_json_matches_dto_schema() -> None:
    report = _rich_report()
    parsed = json.loads(render_json(report))
    assert parsed == report.model_dump(mode="json")


def test_pretty_json_is_indented() -> None:
    rendered = render_json(_rich_report())
    assert rendered.startswith("{\n")
    assert '  "profile": {' in rendered


def test_compact_json_single_line() -> None:
    rendered = render_json(_rich_report(), indent=None)
    assert "\n" not in rendered.rstrip("\n")
    parsed = json.loads(rendered)
    assert parsed == json.loads(render_json(_rich_report()))


def test_ensure_ascii_preserves_non_ascii_characters() -> None:
    report = ReportAssembler().assemble(
        username="octocat",
        snapshot=_rich_snapshot(user=_user(name="Mona—Octocat")),
        profile_readme=_profile_readme(),
    )
    readable = render_json(report, ensure_ascii=False)
    escaped = render_json(report, ensure_ascii=True)
    assert "\u2014" in readable
    assert "\\u2014" in escaped


def test_write_json_writes_pretty_document(tmp_path: Path) -> None:
    report = _rich_report()
    target = write_json(report, tmp_path / "report.json")
    assert target.exists()
    assert target.read_text(encoding="utf-8") == render_json(report)


def test_write_json_supports_compact_output(tmp_path: Path) -> None:
    report = _rich_report()
    target = write_json(report, tmp_path / "compact.json", indent=None)
    assert target.read_text(encoding="utf-8") == render_json(report, indent=None)
