"""Unit tests for the Markdown report renderer (issue #56).

Golden-file tests: a deterministic rich report is rendered to Markdown and
compared byte-for-byte against a checked-in golden file, so formatting changes
are explicit. Additional tests cover deterministic output, section ordering,
severity/priority ordering, honest handling of missing analyses, and the
``write_markdown`` helper.
"""

from __future__ import annotations

from pathlib import Path

from _report_fixtures import NOW, _minimal_report, _rich_report, _userless_report

from ghdtk.analyzers.portfolio import PortfolioComposition, RepositoryCompositionSignals
from ghdtk.analyzers.repository_activity import RepositoryActivity, RepositoryActivitySignals
from ghdtk.analyzers.repository_quality import (
    ReadmeState,
    RepositoryQuality,
    RepositoryQualitySignals,
)
from ghdtk.models.derived import ProfileAnalyses, ProfileAnalysis, Report
from ghdtk.report import render_markdown, write_markdown
from ghdtk.report.markdown import _days, _f, _fmt_bytes, _pct, _yes_no

_GOLDEN_DIR = Path(__file__).parent / "golden"
_GOLDEN_PATH = _GOLDEN_DIR / "rich_profile.md"


def _golden() -> str:
    return _GOLDEN_PATH.read_text(encoding="utf-8")


def test_rich_report_matches_golden_markdown() -> None:
    rendered = render_markdown(_rich_report())
    assert rendered == _golden()


def test_output_is_deterministic() -> None:
    assert render_markdown(_rich_report()) == render_markdown(_rich_report())


def test_header_lists_profile_and_metadata() -> None:
    lines = render_markdown(_rich_report()).splitlines()
    assert lines[0] == "# GitHub Profile Report: octocat"
    assert "ghdtk" in lines[2]
    assert "2026-01-01 12:00:00 UTC" in lines[2]


def test_sections_appear_in_canonical_order() -> None:
    rendered = render_markdown(_rich_report())
    section_markers = [
        "## Overall score",
        "## Dimension scores",
        "## Synthesis",
        "## Findings",
        "## Recommendations",
        "## Analyses",
        "## Metrics",
    ]
    positions = [rendered.index(marker) for marker in section_markers]
    assert positions == sorted(positions)


def test_analysis_sections_follow_canonical_analyzer_order() -> None:
    rendered = render_markdown(_rich_report())
    markers = [
        "### Profile presence",
        "### Profile README",
        "### Repository quality",
        "### Repository activity",
        "### Portfolio composition",
        "### Stars",
        "### Star growth",
        "### Network",
        "### Commits",
        "### Contribution calendar",
        "### Pull requests",
        "### Issues",
        "### Languages",
        "### Technology",
    ]
    positions = [rendered.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_findings_are_ordered_by_severity_then_id() -> None:
    rendered = render_markdown(_rich_report())
    block = rendered.split("## Analyses")[0]
    findings_block = block.split("## Findings")[1].split("## Recommendations")[0]
    severities: list[str] = []
    for line in findings_block.splitlines():
        if line.startswith("### [") and line.endswith("]"):
            rest = line[len("### [") :]
            severities.append(rest.split("]")[0])
    ranks = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    ordered = [ranks[severity] for severity in severities]
    assert ordered == sorted(ordered)


def test_recommendations_are_numbered_by_priority() -> None:
    rendered = render_markdown(_rich_report())
    block = rendered.split("## Analyses")[0]
    recommendations_block = block.split("## Recommendations")[1].split("## Metrics")[0]
    priorities: list[str] = []
    for line in recommendations_block.splitlines():
        if line.startswith("**Priority:**"):
            priorities.append(line.split("**Priority:**")[1].split("·")[0].strip().lower())
    ranks = {"high": 0, "medium": 1, "low": 2}
    ordered = [ranks[priority] for priority in priorities]
    assert ordered == sorted(ordered)


def test_metrics_section_flattens_every_metric() -> None:
    report = _rich_report()
    rendered = render_markdown(report)
    metrics_block = rendered.split("## Metrics")[1]
    data_rows = [
        line for line in metrics_block.splitlines() if line.startswith("| ") and "---" not in line
    ]
    assert len(data_rows) == len(report.profile.metrics) + 1
    assert "presence.completeness" in metrics_block
    assert "commit_activity.total_commits" in metrics_block


def test_overall_score_and_contribution_table_rendered() -> None:
    rendered = render_markdown(_rich_report())
    assert "**" in rendered.split("## Overall score")[1].splitlines()[2]
    assert "| Dimension    | Score | Weight | Contribution |" in rendered


def test_userless_report_omits_presence_sections() -> None:
    rendered = render_markdown(_userless_report())
    assert "### Profile presence" not in rendered
    assert "### Profile README" not in rendered
    assert "## Overall score" in rendered
    assert "## Metrics" in rendered


def test_minimal_report_still_renders_complete_document() -> None:
    rendered = render_markdown(_minimal_report())
    assert rendered.startswith("# GitHub Profile Report: ghost")
    assert "## Overall score" in rendered
    assert "## Findings" in rendered
    assert "## Recommendations" in rendered
    assert "## Analyses" in rendered
    assert "## Metrics" in rendered


def test_write_markdown_writes_utf8_file(tmp_path: Path) -> None:
    target = write_markdown(_rich_report(), tmp_path / "report.md")
    assert target.exists()
    assert target.read_text(encoding="utf-8") == render_markdown(_rich_report())


def test_golden_file_is_checked_in() -> None:
    assert _GOLDEN_PATH.exists()
    assert _golden()


def _edge_analyses_report() -> Report:
    """Analyses exercising the fork/archived/unknown/placeholder state branches."""
    activity = RepositoryActivity(
        username="octocat",
        signals=[
            RepositoryActivitySignals(
                full_name="octocat/forked",
                age_days=None,
                staleness_days=None,
                fork=True,
                archived=False,
            ),
            RepositoryActivitySignals(
                full_name="octocat/old",
                age_days=5,
                staleness_days=2,
                fork=False,
                archived=True,
            ),
            RepositoryActivitySignals(
                full_name="octocat/opaque",
                age_days=1,
                staleness_days=1,
                fork=False,
                archived=False,
                active=False,
                stale=False,
                unknown=True,
            ),
        ],
        metrics=[],
        findings=[],
    )
    portfolio = PortfolioComposition(
        username="octocat",
        signals=[
            RepositoryCompositionSignals(
                full_name="octocat/forked", stars=0, fork=True, archived=False
            ),
            RepositoryCompositionSignals(
                full_name="octocat/old", stars=1, fork=False, archived=True
            ),
        ],
        standouts=["octocat/old"],
        metrics=[],
        findings=[],
    )
    quality = RepositoryQuality(
        username="octocat",
        signals=[
            RepositoryQualitySignals(
                full_name="octocat/placeholder",
                has_description=True,
                description_placeholder=True,
                readme=ReadmeState.PRESENT,
                topics_count=0,
                has_license=False,
                has_homepage=False,
            )
        ],
        metrics=[],
        findings=[],
    )
    profile = ProfileAnalysis(
        username="octocat",
        analyzed_at=NOW,
        analyses=ProfileAnalyses(
            repository_activity=activity,
            portfolio=portfolio,
            repository_quality=quality,
        ),
    )
    return Report(generated_at=NOW, profile=profile)


def test_edge_analyses_render_state_branches() -> None:
    rendered = render_markdown(_edge_analyses_report())
    assert "placeholder" in rendered
    assert "| octocat/forked" in rendered and "fork" in rendered
    assert "archived" in rendered
    assert "unknown" in rendered
    assert "—" in rendered
    assert "**Standout repositories:** octocat/old" in rendered


def _sparse_report() -> Report:
    """A report with no analyses, score, findings, recommendations or metrics."""
    profile = ProfileAnalysis(username="octocat", analyzed_at=NOW)
    return Report(generated_at=NOW, profile=profile)


def test_sparse_report_omits_empty_sections() -> None:
    rendered = render_markdown(_sparse_report())
    assert "No overall score is available for this profile." in rendered
    assert "## Findings" not in rendered
    assert "## Recommendations" not in rendered
    assert "## Analyses" not in rendered
    assert "## Metrics" not in rendered


def test_formatting_helpers_handle_none() -> None:
    assert _f(None) == "—"
    assert _pct(None) == "—"
    assert _days(None) == "—"
    assert _yes_no(None) == "—"
    assert _fmt_bytes(500) == "500 B"
