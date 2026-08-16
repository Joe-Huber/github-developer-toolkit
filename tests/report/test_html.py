"""Smoke tests for the HTML dashboard export (issue #57).

Verifies the rendered document is a self-contained, deterministic, static
HTML page: inline styles only, no external resources, server-rendered CSS
charts for the key dimensions, collapsible findings/recommendations, full
metrics table, and safe HTML escaping of user content.
"""

from __future__ import annotations

from pathlib import Path

from _report_fixtures import _minimal_report, _profile_readme, _repo, _rich_report, _rich_snapshot

from ghdtk.report import ReportAssembler, render_html, write_html


def test_renders_self_contained_html_document() -> None:
    rendered = render_html(_rich_report())
    assert rendered.startswith("<!DOCTYPE html>")
    assert "<html" in rendered and "</html>" in rendered
    assert "<head>" in rendered and "<style>" in rendered
    assert "<title>GitHub Profile Report: octocat</title>" in rendered
    assert rendered.endswith("</html>\n")


def test_no_external_resources() -> None:
    rendered = render_html(_rich_report())
    assert 'src="http' not in rendered
    assert 'href="http' not in rendered
    assert "cdn." not in rendered
    assert "<script" not in rendered


def test_renders_chart_sections() -> None:
    rendered = render_html(_rich_report())
    assert "Dimension scores" in rendered
    assert "Monthly contributions" in rendered
    assert "Language distribution" in rendered
    assert "Most-starred repositories" in rendered
    assert "Technology domains" in rendered
    assert 'class="bar-fill"' in rendered


def test_chart_bars_are_scaled_to_data() -> None:
    rendered = render_html(_rich_report())
    assert 'style="width: 100%"' in rendered
    assert 'style="width: 62%"' in rendered
    assert 'style="width: 38%"' in rendered


def test_findings_and_recommendations_are_collapsible() -> None:
    rendered = render_html(_rich_report())
    assert rendered.count("<details>") >= 2
    assert "Findings" in rendered
    assert "Recommendations" in rendered


def test_metrics_table_lists_every_metric() -> None:
    report = _rich_report()
    rendered = render_html(report)
    metrics_block = rendered.split("Metrics</h2>")[1].split("</section>")[0]
    assert metrics_block.count("<tr>") == len(report.profile.metrics) + 1
    assert "presence.completeness" in metrics_block
    assert "commit_activity.total_commits" in metrics_block


def test_overall_score_rendered() -> None:
    rendered = render_html(_rich_report())
    assert 'class="score-value"' in rendered
    assert "out of 100" in rendered


def test_user_content_is_escaped() -> None:
    report = ReportAssembler().assemble(
        username="oct<cat",
        snapshot=_rich_snapshot(
            username="oct<cat",
            repositories=[_repo(full_name="oct<cat/toolkit")],
        ),
        profile_readme=_profile_readme(),
    )
    rendered = render_html(report)
    assert "&lt;cat" in rendered
    assert "<cat" not in rendered
    assert "oct<cat" not in rendered


def test_output_is_deterministic() -> None:
    assert render_html(_rich_report()) == render_html(_rich_report())


def test_minimal_report_renders_complete_document() -> None:
    rendered = render_html(_minimal_report())
    assert rendered.startswith("<!DOCTYPE html>")
    assert "<title>GitHub Profile Report: ghost</title>" in rendered
    assert 'class="score-value"' in rendered
    assert "Findings" in rendered
    assert "Recommendations" in rendered
    assert "Metrics" in rendered


def test_write_html_writes_utf8_file(tmp_path: Path) -> None:
    target = write_html(_rich_report(), tmp_path / "report.html")
    assert target.exists()
    assert target.read_text(encoding="utf-8") == render_html(_rich_report())
