"""HTML report renderer / dashboard export (issue #57).

Renders the :class:`Report` DTO into a self-contained static HTML document
with an interactive feel: collapsible detail sections and CSS bar charts for
dimension scores, monthly contributions, language distribution and the
most-starred ranking. The document embeds all styles inline and references no
external resources, so it works fully offline and is deterministic — identical
reports render byte-identical HTML. All dynamic content is HTML-escaped.
"""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from ghdtk.models.derived import (
    DimensionId,
    DimensionScore,
    Finding,
    MetricRecord,
    OverallScore,
    Recommendation,
    Report,
)

if TYPE_CHECKING:
    from ghdtk.analyzers.commits import CommitActivity
    from ghdtk.analyzers.contribution_calendar import ContributionCalendarAnalysis
    from ghdtk.analyzers.languages import LanguageDistributionAnalysis
    from ghdtk.analyzers.network import FollowerNetwork
    from ghdtk.analyzers.presence import ProfilePresence
    from ghdtk.analyzers.repository_quality import RepositoryQuality
    from ghdtk.analyzers.stars import StarsAnalysis
    from ghdtk.analyzers.technology import TechnologyDiversityAnalysis
    from ghdtk.models.derived.analyses import ProfileAnalyses

_SEVERITY_RANK: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}

_PRIORITY_RANK: dict[str, int] = {"high": 0, "medium": 1, "low": 2}

_CSS = """
:root {
  --bg: #0d1117; --panel: #161b22; --border: #30363d; --text: #e6edf3;
  --muted: #8b949e; --accent: #58a6ff; --good: #3fb950; --bad: #f85149;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  line-height: 1.5;
}
header { padding: 2rem 1.5rem 1rem; border-bottom: 1px solid var(--border); }
main { max-width: 960px; margin: 0 auto; padding: 1.5rem; }
h1 { margin: 0; font-size: 1.6rem; }
h2 {
  margin: 2rem 0 0.75rem; font-size: 1.15rem;
  border-bottom: 1px solid var(--border); padding-bottom: 0.4rem;
}
.meta { color: var(--muted); margin: 0.25rem 0 0; font-size: 0.85rem; }
.score-card { display: flex; align-items: baseline; gap: 1rem; margin: 1rem 0; }
.score-value { font-size: 2.6rem; font-weight: 700; }
.score-note { color: var(--muted); }
table { border-collapse: collapse; width: 100%; margin: 0.75rem 0; font-size: 0.9rem; }
th, td {
  text-align: left; padding: 0.4rem 0.6rem;
  border-bottom: 1px solid var(--border);
}
th { color: var(--muted); font-weight: 600; }
.bar-row {
  display: grid; grid-template-columns: 12rem 1fr 3.5rem;
  align-items: center; gap: 0.75rem; margin: 0.4rem 0;
}
.bar-label {
  font-size: 0.9rem; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis;
}
.bar-track {
  background: var(--panel); border: 1px solid var(--border);
  border-radius: 6px; height: 1.1rem; overflow: hidden;
}
.bar-fill { display: block; height: 100%; background: var(--accent); border-radius: 5px; }
.bar-value { font-size: 0.85rem; color: var(--muted); text-align: right; }
details {
  margin: 0.5rem 0; border: 1px solid var(--border); border-radius: 6px;
  padding: 0.6rem 0.9rem; background: var(--panel);
}
summary { cursor: pointer; font-weight: 600; }
ul { margin: 0.25rem 0; padding-left: 1.25rem; }
li { margin: 0.3rem 0; }
.severity {
  display: inline-block; font-size: 0.75rem; font-weight: 700;
  padding: 0.1rem 0.5rem; border-radius: 10px;
}
.severity-high, .severity-critical { background: var(--bad); color: #fff; }
.severity-medium { background: #d29922; color: #1c2128; }
.severity-low { background: #58a6ff; color: #0d1117; }
.severity-info { background: var(--border); color: var(--text); }
.pill {
  display: inline-block; font-size: 0.75rem; padding: 0.1rem 0.5rem;
  border-radius: 10px; border: 1px solid var(--border); color: var(--muted);
}
.pill-high { border-color: var(--bad); color: var(--bad); }
.pill-medium { border-color: #d29922; color: #d29922; }
.pill-low { border-color: var(--muted); color: var(--muted); }
.empty { color: var(--muted); font-style: italic; }
.footer { color: var(--muted); font-size: 0.8rem; text-align: center; padding: 2rem 0 1.5rem; }
"""


def _escape(value: object) -> str:
    return escape(str(value), quote=True)


def _f(value: float | int | None, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.0f}%"


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(UTC)
    return f"{value:%Y-%m-%d %H:%M:%S} UTC"


def _dimension_label(dimension: DimensionId) -> str:
    return dimension.value.replace("_", " ").title()


def _bar_row(label: str, value: float, width_percent: float, max_label: str | None = None) -> str:
    width = min(100.0, max(0.0, width_percent))
    display = max_label or _f(value)
    return (
        '<div class="bar-row">'
        f'<span class="bar-label" title="{_escape(label)}">{_escape(label)}</span>'
        '<div class="bar-track">'
        f'<span class="bar-fill" style="width: {width:.0f}%"></span>'
        "</div>"
        f'<span class="bar-value">{_escape(display)}</span>'
        "</div>"
    )


def _bar_chart(rows: list[tuple[str, float, float, str]]) -> str:
    if not rows:
        return '<p class="empty">No data to chart.</p>'
    return "\n".join(
        _bar_row(label, value, width, max_label) for label, value, width, max_label in rows
    )


def _dimension_chart(scores: list[DimensionScore]) -> str:
    return _bar_chart(
        [
            (_dimension_label(score.dimension), score.score, score.score, f"{score.score:.0f}")
            for score in scores
        ]
    )


def _calendar_chart(analysis: ContributionCalendarAnalysis) -> str:
    pattern = analysis.monthly_pattern
    if not pattern:
        return '<p class="empty">No contribution calendar was collected.</p>'
    months = sorted(pattern)
    maximum = max(pattern.values()) or 1
    rows = []
    for month in months:
        count = pattern[month]
        rows.append((month, float(count), count / maximum * 100, str(count)))
    return _bar_chart(rows)


def _language_chart(analysis: LanguageDistributionAnalysis) -> str:
    if not analysis.distribution:
        return '<p class="empty">No language statistics were collected.</p>'
    rows = [
        (share.language, share.share * 100, share.share * 100, _pct(share.share))
        for share in analysis.distribution
    ]
    return _bar_chart(rows)


def _stars_chart(analysis: StarsAnalysis) -> str:
    if not analysis.ranking:
        return '<p class="empty">No repository stars were collected.</p>'
    maximum = max(entry.stars for entry in analysis.ranking) or 1
    rows = [
        (entry.full_name, float(entry.stars), entry.stars / maximum * 100, str(entry.stars))
        for entry in analysis.ranking
    ]
    return _bar_chart(rows)


def _technology_chart(analysis: TechnologyDiversityAnalysis) -> str:
    if not analysis.domain_shares:
        return '<p class="empty">No technology evidence was collected.</p>'
    rows = [
        (share.domain, share.share * 100, share.share * 100, _pct(share.share))
        for share in analysis.domain_shares
    ]
    return _bar_chart(rows)


def _presence_section(analysis: ProfilePresence | None) -> str:
    if analysis is None:
        return ""
    rows = [
        "<tr>"
        f"<td>{_escape(field.label)}</td>"
        f'<td><span class="severity severity-{_escape(field.status.value)}">'
        f"{_escape(field.status.value)}</span></td>"
        f"<td>{_escape(field.value or '—')}</td>"
        "</tr>"
        for field in analysis.fields
    ]
    return (
        "<section><h2>Profile presence</h2><table><thead><tr>"
        "<th>Field</th><th>Status</th><th>Value</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></section>"
    )


def _repo_quality_table(analysis: RepositoryQuality | None) -> str:
    if analysis is None:
        return ""
    if not analysis.signals:
        return (
            "<section><h2>Repository quality</h2>"
            '<p class="empty">No repositories were collected.</p></section>'
        )
    rows = []
    for signal in analysis.signals:
        description = "yes" if signal.has_description else "no"
        if signal.description_placeholder:
            description = "placeholder"
        rows.append(
            "<tr>"
            f"<td>{_escape(signal.full_name)}</td>"
            f"<td>{_escape(description)}</td>"
            f"<td>{_escape(signal.readme.value)}</td>"
            f"<td>{signal.topics_count}</td>"
            f"<td>{_escape(signal.license_name or '—')}</td>"
            f"<td>{'yes' if signal.has_homepage else 'no'}</td>"
            "</tr>"
        )
    return (
        "<section><h2>Repository quality</h2><table><thead><tr>"
        "<th>Repository</th><th>Description</th><th>README</th><th>Topics</th><th>License</th><th>Homepage</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></section>"
    )


def _network_section(analysis: FollowerNetwork | None) -> str:
    if analysis is None:
        return ""
    properties = [
        ("Followers", analysis.followers_count),
        ("Following", analysis.following_count),
        (
            "Follower to following ratio",
            _f(analysis.ratio, 2) if analysis.ratio is not None else None,
        ),
        ("Estimated reach", analysis.reach_estimate),
        ("Mutual follows", analysis.mutual_follows),
        ("Org memberships", analysis.orgs_count),
    ]
    rows = "".join(
        f"<tr><td>{_escape(label)}</td><td>{_escape(value or '—')}</td></tr>"
        for label, value in properties
    )
    return f"<section><h2>Network</h2><table><tbody>{rows}</tbody></table></section>"


def _commits_section(analysis: CommitActivity | None) -> str:
    if analysis is None:
        return ""
    properties = [
        ("Total commits collected", analysis.total_commits),
        ("Active days", analysis.active_days),
        (
            "Commits per month",
            _f(analysis.cadence_per_month, 1) if analysis.cadence_per_month is not None else None,
        ),
        (
            "Median gap (days)",
            _f(analysis.median_gap_days, 0) if analysis.median_gap_days is not None else None,
        ),
    ]
    rows = "".join(
        f"<tr><td>{_escape(label)}</td><td>{_escape(value or '—')}</td></tr>"
        for label, value in properties
    )
    return f"<section><h2>Commits</h2><table><tbody>{rows}</tbody></table></section>"


def _overall_card(overall: OverallScore | None) -> str:
    if overall is None:
        return '<p class="empty">No overall score is available for this profile.</p>'
    rows = "".join(
        "<tr>"
        f"<td>{_escape(_dimension_label(contribution.dimension))}</td>"
        f"<td>{_f(contribution.score)}</td>"
        f"<td>{_f(contribution.weight)}</td>"
        f"<td>{_f(contribution.contribution)}</td>"
        "</tr>"
        for contribution in overall.contributions
    )
    table = (
        "<table><thead><tr><th>Dimension</th><th>Score</th><th>Weight</th><th>Contribution</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )
    return (
        '<div class="score-card">'
        f'<span class="score-value">{_f(overall.overall)}</span>'
        '<span class="score-note">out of 100</span>'
        "</div>"
        f"{table}"
    )


def _findings_list(findings: list[Finding]) -> str:
    if not findings:
        return '<p class="empty">No findings.</p>'
    ordered = sorted(
        findings, key=lambda finding: (_SEVERITY_RANK[finding.severity.value], finding.id)
    )
    items = []
    for finding in ordered:
        dimension = (
            f"<li>Dimension: {_escape(_dimension_label(finding.dimension))}</li>"
            if finding.dimension is not None
            else ""
        )
        evidence = (
            (
                "<li>Evidence: "
                + ", ".join(
                    f"<code>{_escape(source.identifier)}</code>" for source in finding.evidence
                )
                + "</li>"
            )
            if finding.evidence
            else ""
        )
        items.append(
            "<details>"
            f'<summary><span class="severity severity-{_escape(finding.severity.value)}">'
            f"{_escape(finding.severity.value.upper())}</span> "
            f"{_escape(finding.title)}</summary>"
            f"<p>{_escape(finding.message)}</p>"
            f"<ul>{dimension}{evidence}</ul>"
            "</details>"
        )
    return "\n".join(items)


def _recommendations_list(recommendations: list[Recommendation]) -> str:
    if not recommendations:
        return '<p class="empty">No recommendations.</p>'
    ordered = sorted(recommendations, key=lambda rec: (_PRIORITY_RANK[rec.priority.value], rec.id))
    items = []
    for rec in ordered:
        items.append(
            "<details>"
            f'<summary><span class="pill pill-{_escape(rec.priority.value)}">'
            f"{_escape(rec.priority.value.upper())}</span> "
            f'<span class="pill">{_escape(rec.effort.value.upper())} effort</span> '
            f"{_escape(rec.action)}</summary>"
            f"<p>{_escape(rec.rationale)}</p>"
            "</details>"
        )
    return "\n".join(items)


def _metrics_table(metrics: list[MetricRecord]) -> str:
    if not metrics:
        return '<p class="empty">No metrics.</p>'

    def cell(metric: MetricRecord) -> str:
        if metric.is_unavailable:
            return "unavailable"
        value = metric.value
        if value is None:
            return "—"
        return _escape(str(value))

    rows = "".join(
        "<tr>"
        f"<td><code>{_escape(metric.id)}</code></td>"
        f"<td>{_escape(metric.label)}</td>"
        f"<td>{cell(metric)}</td>"
        f"<td>{_pct(metric.confidence)}</td>"
        "</tr>"
        for metric in metrics
    )
    return (
        "<table><thead><tr><th>Metric</th><th>Label</th><th>Value</th><th>Confidence</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _analyses_section(analyses: ProfileAnalyses | None, scores: list[DimensionScore]) -> str:
    sections: list[str] = []
    if scores:
        sections.append(
            "<section><h2>Dimension scores</h2>" + _dimension_chart(scores) + "</section>"
        )
    if analyses is None:
        return "\n".join(sections)
    if analyses.contribution_calendar is not None:
        sections.append(
            "<section><h2>Monthly contributions</h2>"
            + _calendar_chart(analyses.contribution_calendar)
            + "</section>"
        )
    if analyses.languages is not None:
        sections.append(
            "<section><h2>Language distribution</h2>"
            + _language_chart(analyses.languages)
            + "</section>"
        )
    if analyses.stars is not None:
        sections.append(
            "<section><h2>Most-starred repositories</h2>"
            + _stars_chart(analyses.stars)
            + "</section>"
        )
    if analyses.technology is not None:
        sections.append(
            "<section><h2>Technology domains</h2>"
            + _technology_chart(analyses.technology)
            + "</section>"
        )
    if analyses.presence is not None:
        sections.append(_presence_section(analyses.presence))
    if analyses.repository_quality is not None:
        sections.append(_repo_quality_table(analyses.repository_quality))
    if analyses.network is not None:
        sections.append(_network_section(analyses.network))
    if analyses.commits is not None:
        sections.append(_commits_section(analyses.commits))
    return "\n".join(sections)


def render_html(report: Report) -> str:
    """Render ``report`` as a self-contained, offline HTML dashboard."""
    profile = report.profile
    title = f"GitHub Profile Report: {profile.username}"
    body = [
        f"<h1>{_escape(title)}</h1>",
        f'<p class="meta">ghdtk {_escape(report.tool_version)} · '
        f"generated {_escape(_format_datetime(report.generated_at))} · "
        f"analyzed {_escape(_format_datetime(profile.analyzed_at))}</p>",
        "<section><h2>Overall score</h2>" + _overall_card(profile.overall) + "</section>",
        _analyses_section(profile.analyses, profile.scores),
        "<section><h2>Findings</h2>" + _findings_list(profile.findings) + "</section>",
        "<section><h2>Recommendations</h2>"
        + _recommendations_list(profile.recommendations)
        + "</section>",
        "<section><h2>Metrics</h2>" + _metrics_table(profile.metrics) + "</section>",
        '<p class="footer">Rendered by ghdtk — a fully static report, no external resources.</p>',
    ]
    sections = "\n".join(body[2:])
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_escape(title)}</title>\n"
        f"<style>{_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        "<header>\n"
        f"{body[0]}\n"
        f"{body[1]}\n"
        "</header>\n"
        "<main>\n"
        f"{sections}\n"
        "</main>\n"
        "</body>\n"
        "</html>\n"
    )


def write_html(report: Report, path: str | Path) -> Path:
    """Render ``report`` to HTML and write it to ``path``."""
    target = Path(path)
    target.write_text(render_html(report), encoding="utf-8")
    return target


__all__ = ["render_html", "write_html"]
