"""Markdown report renderer (issue #56).

Renders the serializable :class:`Report` DTO into complete, well-formatted
GitHub-flavored Markdown for humans: the overall score and contribution
table, dimension score breakdowns, synthesis, findings, prioritized
recommendations, a per-analysis detail section and a flattened metric table
with provenance. Output is deterministic — the derived models are frozen and
field-ordered, so identical reports render byte-identical Markdown.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ghdtk.models.derived import (
    DimensionId,
    DimensionScore,
    Finding,
    MetricRecord,
    MetricValue,
    OverallScore,
    Recommendation,
    Report,
    SourceReference,
    Synthesis,
)

if TYPE_CHECKING:
    from ghdtk.analyzers.commits import CommitActivity
    from ghdtk.analyzers.contribution_calendar import ContributionCalendarAnalysis
    from ghdtk.analyzers.issues import IssueParticipationAnalysis
    from ghdtk.analyzers.languages import LanguageDistributionAnalysis
    from ghdtk.analyzers.network import FollowerNetwork
    from ghdtk.analyzers.portfolio import (
        PortfolioComposition,
        RepositoryCompositionSignals,
    )
    from ghdtk.analyzers.presence import ProfilePresence
    from ghdtk.analyzers.pull_requests import PullRequestAnalysis
    from ghdtk.analyzers.readme import ReadmeAssessment
    from ghdtk.analyzers.repository_activity import (
        RepositoryActivity,
        RepositoryActivitySignals,
    )
    from ghdtk.analyzers.repository_quality import (
        RepositoryQuality,
    )
    from ghdtk.analyzers.star_growth import StarGrowthAnalysis
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

_PRESENCE_PROPERTIES: tuple[str, ...] = (
    "presence.completeness",
    "presence.fields.total",
    "presence.fields.present",
    "presence.fields.missing",
    "presence.fields.placeholder",
    "presence.account_age_days",
)

_README_PROPERTIES: tuple[str, ...] = (
    "readme.word_count",
    "readme.headings",
    "readme.code_blocks",
    "readme.links",
    "readme.images",
    "readme.badges",
    "readme.section.about",
    "readme.section.skills",
    "readme.section.contact",
    "readme.username_mentions",
)

_REPOSITORY_QUALITY_PROPERTIES: tuple[str, ...] = (
    "portfolio.repositories.count",
    "portfolio.quality.description_coverage",
    "portfolio.quality.readme_coverage",
    "portfolio.quality.license_coverage",
    "portfolio.quality.homepage_coverage",
    "portfolio.quality.topics.average",
    "portfolio.quality.placeholder_descriptions",
)

_REPOSITORY_ACTIVITY_PROPERTIES: tuple[str, ...] = (
    "portfolio.activity.repos.total",
    "portfolio.activity.repos.active",
    "portfolio.activity.repos.dormant",
    "portfolio.activity.pushed_recently_30d",
    "portfolio.activity.pushed_90d",
    "portfolio.activity.pushed_365d",
    "portfolio.activity.pushed_over_365d",
    "portfolio.activity.median_age_days",
    "portfolio.activity.median_staleness_days",
    "portfolio.activity.max_staleness_days",
)

_PORTFOLIO_PROPERTIES: tuple[str, ...] = (
    "portfolio.composition.repos.total",
    "portfolio.composition.own_count",
    "portfolio.composition.fork_count",
    "portfolio.composition.archived_count",
    "portfolio.composition.total_stars",
    "portfolio.composition.top_repo_stars",
    "portfolio.composition.top_repo_share",
    "portfolio.composition.star_concentration",
    "portfolio.composition.fork_ratio",
    "portfolio.standout.count",
)

_STARS_PROPERTIES: tuple[str, ...] = (
    "portfolio.stars.total",
    "portfolio.stars.repos_with_stars",
    "portfolio.stars.repos_zero",
    "portfolio.stars.average",
    "portfolio.stars.median",
    "portfolio.stars.max",
    "portfolio.stars.fork_stars",
    "portfolio.stars.fork_star_share",
)

_STAR_GROWTH_PROPERTIES: tuple[str, ...] = (
    "star_growth.timeline_repo",
    "star_growth.observed_stars",
    "star_growth.reported_stars",
    "star_growth.coverage",
    "star_growth.trend",
    "star_growth.stars_30d",
    "star_growth.stars_90d",
    "star_growth.stars_365d",
)

_NETWORK_PROPERTIES: tuple[str, ...] = (
    "network.followers.count",
    "network.following.count",
    "network.followers.ratio",
    "network.followers.reach",
    "network.followers.sample",
    "network.followers.coverage",
    "network.mutual_follows.count",
    "network.orgs.count",
)

_COMMITS_PROPERTIES: tuple[str, ...] = (
    "commit_activity.total_commits",
    "commit_activity.repos_collected",
    "commit_activity.repos_with_commits",
    "commit_activity.coverage_start",
    "commit_activity.coverage_end",
    "commit_activity.span_days",
    "commit_activity.active_days",
    "commit_activity.cadence_per_month",
    "commit_activity.median_gap_days",
    "commit_activity.longest_gap_days",
    "commit_activity.top_repo",
)

_CALENDAR_PROPERTIES: tuple[str, ...] = (
    "contribution_calendar.total_contributions",
    "contribution_calendar.active_days",
    "contribution_calendar.total_days",
    "contribution_calendar.density",
    "contribution_calendar.current_streak",
    "contribution_calendar.longest_streak",
    "contribution_calendar.longest_gap_days",
    "contribution_calendar.restricted_contributions",
)

_PULL_REQUEST_PROPERTIES: tuple[str, ...] = (
    "pull_requests.total_pull_requests",
    "pull_requests.open_count",
    "pull_requests.merged_count",
    "pull_requests.closed_unmerged_count",
    "pull_requests.merge_rate",
    "pull_requests.median_time_to_merge_days",
    "pull_requests.external_count",
    "pull_requests.external_share",
    "pull_requests.repository_diversity",
    "pull_requests.review_comments_total",
    "pull_requests.reviewed_share",
    "pull_requests.comments_total",
    "pull_requests.coverage_start",
    "pull_requests.coverage_end",
)

_ISSUES_PROPERTIES: tuple[str, ...] = (
    "issues.total_issues",
    "issues.open_count",
    "issues.closed_count",
    "issues.close_rate",
    "issues.median_close_days",
    "issues.oldest_open_days",
    "issues.total_comments",
    "issues.commented_share",
    "issues.external_share",
    "issues.repository_diversity",
    "issues.coverage_start",
    "issues.coverage_end",
)

_LANGUAGES_PROPERTIES: tuple[str, ...] = (
    "languages.total_bytes",
    "languages.distinct_languages",
    "languages.dominant_language",
    "languages.dominant_share",
    "languages.repos.with_byte_stats",
    "languages.repos.declared_only",
    "languages.repos.unknown",
    "languages.repos.empty",
)

_TECHNOLOGY_PROPERTIES: tuple[str, ...] = (
    "tech.domains_count",
    "tech.top_domain",
    "tech.top_domain_share",
    "tech.simpson_index",
    "tech.mapped_share",
    "tech.unmapped_share",
    "tech.total_bytes",
    "tech.mapped_bytes",
    "tech.unmapped_bytes",
)

#: Property metric ids whose values are 0..1 fractions rendered as percentages.
_PERCENT_METRIC_IDS: frozenset[str] = frozenset(
    {
        "contribution_calendar.density",
        "issues.close_rate",
        "issues.commented_share",
        "issues.external_share",
        "languages.dominant_share",
        "network.followers.coverage",
        "portfolio.composition.fork_ratio",
        "portfolio.composition.star_concentration",
        "portfolio.quality.description_coverage",
        "portfolio.quality.homepage_coverage",
        "portfolio.quality.license_coverage",
        "portfolio.quality.readme_coverage",
        "portfolio.stars.fork_star_share",
        "pull_requests.external_share",
        "pull_requests.merge_rate",
        "pull_requests.reviewed_share",
        "star_growth.coverage",
        "tech.mapped_share",
        "tech.top_domain_share",
        "tech.unmapped_share",
    }
)


def _f(value: float | int | None, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.0f}%"


def _days(value: int | None) -> str:
    if value is None:
        return "—"
    return str(value)


def _yes_no(value: bool | None) -> str:
    if value is None:
        return "—"
    return "yes" if value else "no"


def _raw_number(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _metric_value(value: MetricValue) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return _yes_no(value)
    if isinstance(value, float):
        return _raw_number(value)
    return str(value)


def _property_value(metric_id: str, value: MetricValue) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return _yes_no(value)
    if isinstance(value, float):
        if metric_id in _PERCENT_METRIC_IDS:
            return _pct(value)
        return _raw_number(value)
    return str(value)


def _fmt_bytes(value: int) -> str:
    amount = float(value)
    units = ("B", "kB", "MB", "GB", "TB")
    index = 0
    while amount >= 1000 and index < len(units) - 1:
        index += 1
        amount /= 1000
    if index == 0:
        return f"{value} B"
    return f"{amount:.1f} {units[index]}"


def _dimension_label(dimension: DimensionId) -> str:
    return dimension.value.replace("_", " ").title()


def _severity_label(severity: str) -> str:
    return severity.upper()


def _source_text(source: SourceReference) -> str:
    text = f"{source.entity.value}:{source.identifier}"
    if source.field:
        text = f"{text}#{source.field}"
    return text


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(UTC)
    return f"{value:%Y-%m-%d %H:%M:%S} UTC"


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    lines = [
        "| " + " | ".join(header.ljust(widths[i]) for i, header in enumerate(headers)) + " |",
        "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) + " |")
    return lines


def _properties(metrics: list[MetricRecord], ids: tuple[str, ...]) -> list[list[str]]:
    by_id = {metric.id: metric for metric in metrics}
    rows: list[list[str]] = []
    for metric_id in ids:
        metric = by_id.get(metric_id)
        if metric is not None:
            rows.append([metric.label, _property_value(metric.id, metric.value)])
    return rows


def _render_properties(lines: list[str], metrics: list[MetricRecord], ids: tuple[str, ...]) -> None:
    rows = _properties(metrics, ids)
    if not rows:
        return
    lines.extend(_table(["Property", "Value"], rows))
    lines.append("")


def _render_overall(lines: list[str], overall: OverallScore | None) -> None:
    lines.append("## Overall score")
    lines.append("")
    if overall is None:
        lines.append("No overall score is available for this profile.")
        lines.append("")
        return
    lines.append(f"**{_f(overall.overall)} / 100**")
    lines.append("")
    if overall.contributions:
        lines.extend(
            _table(
                ["Dimension", "Score", "Weight", "Contribution"],
                [
                    [
                        _dimension_label(contribution.dimension),
                        _f(contribution.score),
                        _f(contribution.weight),
                        _f(contribution.contribution),
                    ]
                    for contribution in overall.contributions
                ],
            )
        )
        lines.append("")
    if overall.strengths:
        lines.append("**Strengths**")
        lines.append("")
        for strength in overall.strengths:
            lines.append(f"- {strength}")
        lines.append("")
    if overall.weaknesses:
        lines.append("**Weaknesses**")
        lines.append("")
        for weakness in overall.weaknesses:
            lines.append(f"- {weakness}")
        lines.append("")


def _render_dimension_scores(lines: list[str], scores: list[DimensionScore]) -> None:
    if not scores:
        return
    lines.append("## Dimension scores")
    lines.append("")
    for score in scores:
        lines.append(f"### {_dimension_label(score.dimension)} — {_f(score.score)} / 100")
        lines.append("")
        if score.rationale:
            lines.append(score.rationale)
            lines.append("")
        if score.breakdown:
            rows = [
                [
                    component.label,
                    _f(component.weight),
                    _f(component.contribution),
                    _source_text(component.sources[0]) if component.sources else "—",
                ]
                for component in score.breakdown
            ]
            lines.extend(_table(["Component", "Weight", "Contribution", "Source"], rows))
            lines.append("")


def _render_synthesis(lines: list[str], synthesis: Synthesis | None) -> None:
    if synthesis is None:
        return
    lines.append("## Synthesis")
    lines.append("")
    if synthesis.strengths:
        lines.append("**Strengths**")
        lines.append("")
        for strength in synthesis.strengths:
            lines.append(f"- {strength}")
        lines.append("")
    if synthesis.weaknesses:
        lines.append("**Weaknesses**")
        lines.append("")
        for weakness in synthesis.weaknesses:
            lines.append(f"- {weakness}")
        lines.append("")
    if synthesis.red_flags:
        lines.append("**Red flags**")
        lines.append("")
        for red_flag in synthesis.red_flags:
            lines.append(f"- {red_flag}")
        lines.append("")


def _render_findings(lines: list[str], findings: list[Finding]) -> None:
    if not findings:
        return
    lines.append("## Findings")
    lines.append("")
    ordered = sorted(
        findings, key=lambda finding: (_SEVERITY_RANK[finding.severity.value], finding.id)
    )
    for finding in ordered:
        lines.append(f"### [{_severity_label(finding.severity.value)}] {finding.title}")
        lines.append("")
        lines.append(finding.message)
        lines.append("")
        if finding.dimension is not None:
            lines.append(f"- **Dimension:** {_dimension_label(finding.dimension)}")
        if finding.evidence:
            evidence = ", ".join(_source_text(source) for source in finding.evidence)
            lines.append(f"- **Evidence:** {evidence}")
        lines.append("")


def _render_recommendations(lines: list[str], recommendations: list[Recommendation]) -> None:
    if not recommendations:
        return
    lines.append("## Recommendations")
    lines.append("")
    ordered = sorted(recommendations, key=lambda rec: (_PRIORITY_RANK[rec.priority.value], rec.id))
    for index, rec in enumerate(ordered, start=1):
        lines.append(f"### {index}. {rec.action}")
        lines.append("")
        lines.append(
            f"**Priority:** {rec.priority.value.upper()} · **Effort:** {rec.effort.value.upper()}"
        )
        lines.append("")
        lines.append(f"**Why:** {rec.rationale}")
        lines.append("")
        if rec.finding_ids:
            lines.append(f"- **Findings:** {', '.join(rec.finding_ids)}")
        if rec.metric_ids:
            lines.append(f"- **Metrics:** {', '.join(rec.metric_ids)}")
        if rec.sources:
            evidence = ", ".join(_source_text(source) for source in rec.sources)
            lines.append(f"- **Evidence:** {evidence}")
        lines.append("")


def _render_presence(lines: list[str], analysis: ProfilePresence) -> None:
    lines.append("### Profile presence")
    lines.append("")
    rows = [[field.label, field.status.value, field.value or "—"] for field in analysis.fields]
    lines.extend(_table(["Field", "Status", "Value"], rows))
    lines.append("")
    _render_properties(lines, analysis.metrics, _PRESENCE_PROPERTIES)


def _render_readme(lines: list[str], analysis: ReadmeAssessment) -> None:
    lines.append("### Profile README")
    lines.append("")
    lines.append(f"- **Status:** {analysis.status.value.replace('_', ' ')}")
    lines.append("")
    _render_properties(lines, analysis.metrics, _README_PROPERTIES)


def _render_repository_quality(lines: list[str], analysis: RepositoryQuality) -> None:
    lines.append("### Repository quality")
    lines.append("")
    _render_properties(lines, analysis.metrics, _REPOSITORY_QUALITY_PROPERTIES)
    if not analysis.signals:
        lines.append("No repositories were collected.")
        lines.append("")
        return
    rows = []
    for signal in analysis.signals:
        description = "yes" if signal.has_description else "no"
        if signal.description_placeholder:
            description = "placeholder"
        rows.append(
            [
                signal.full_name,
                description,
                signal.readme.value,
                str(signal.topics_count),
                signal.license_name or "—",
                _yes_no(signal.has_homepage),
            ]
        )
    lines.extend(
        _table(["Repository", "Description", "README", "Topics", "License", "Homepage"], rows)
    )
    lines.append("")


def _activity_state(signal: RepositoryActivitySignals) -> str:
    if signal.fork:
        return "fork"
    if signal.archived:
        return "archived"
    if signal.active:
        return "active"
    if signal.stale:
        return "stale"
    return "unknown"


def _render_repository_activity(lines: list[str], analysis: RepositoryActivity) -> None:
    lines.append("### Repository activity")
    lines.append("")
    _render_properties(lines, analysis.metrics, _REPOSITORY_ACTIVITY_PROPERTIES)
    if not analysis.signals:
        lines.append("No repositories were collected.")
        lines.append("")
        return
    rows = [
        [
            signal.full_name,
            _days(signal.age_days),
            _days(signal.staleness_days),
            _activity_state(signal),
        ]
        for signal in analysis.signals
    ]
    lines.extend(_table(["Repository", "Age (days)", "Last push (days)", "State"], rows))
    lines.append("")


def _composition_state(signal: RepositoryCompositionSignals) -> str:
    if signal.fork:
        return "fork"
    if signal.archived:
        return "archived"
    return "—"


def _render_portfolio(lines: list[str], analysis: PortfolioComposition) -> None:
    lines.append("### Portfolio composition")
    lines.append("")
    _render_properties(lines, analysis.metrics, _PORTFOLIO_PROPERTIES)
    rows = [
        [signal.full_name, str(signal.stars), _composition_state(signal)]
        for signal in analysis.signals
    ]
    lines.extend(_table(["Repository", "Stars", "State"], rows))
    lines.append("")
    if analysis.standouts:
        lines.append(f"**Standout repositories:** {', '.join(analysis.standouts)}")
        lines.append("")


def _render_stars(lines: list[str], analysis: StarsAnalysis) -> None:
    lines.append("### Stars")
    lines.append("")
    _render_properties(lines, analysis.metrics, _STARS_PROPERTIES)
    if analysis.ranking:
        rows = [
            [
                str(entry.rank),
                entry.full_name,
                str(entry.stars),
                _yes_no(entry.fork),
                _yes_no(entry.archived),
            ]
            for entry in analysis.ranking
        ]
        lines.extend(_table(["Rank", "Repository", "Stars", "Fork", "Archived"], rows))
        lines.append("")


def _render_star_growth(lines: list[str], analysis: StarGrowthAnalysis) -> None:
    lines.append("### Star growth")
    lines.append("")
    lines.append(f"- **Status:** {analysis.status.value.replace('_', ' ')}")
    lines.append("")
    _render_properties(lines, analysis.metrics, _STAR_GROWTH_PROPERTIES)


def _render_network(lines: list[str], analysis: FollowerNetwork) -> None:
    lines.append("### Network")
    lines.append("")
    _render_properties(lines, analysis.metrics, _NETWORK_PROPERTIES)


def _render_commits(lines: list[str], analysis: CommitActivity) -> None:
    lines.append("### Commits")
    lines.append("")
    _render_properties(lines, analysis.metrics, _COMMITS_PROPERTIES)
    if analysis.per_repo_commits:
        rows = [[name, str(count)] for name, count in analysis.per_repo_commits.items()]
        lines.extend(_table(["Repository", "Commits"], rows))
        lines.append("")
    if analysis.weekday_counts:
        rows = [[weekday, str(count)] for weekday, count in analysis.weekday_counts.items()]
        lines.extend(_table(["Weekday", "Commits"], rows))
        lines.append("")
    if analysis.hour_bucket_counts:
        rows = [[bucket, str(count)] for bucket, count in analysis.hour_bucket_counts.items()]
        lines.extend(_table(["Hour (UTC)", "Commits"], rows))
        lines.append("")


def _render_calendar(lines: list[str], analysis: ContributionCalendarAnalysis) -> None:
    lines.append("### Contribution calendar")
    lines.append("")
    _render_properties(lines, analysis.metrics, _CALENDAR_PROPERTIES)
    if analysis.monthly_pattern:
        rows = [[month, str(count)] for month, count in analysis.monthly_pattern.items()]
        lines.extend(_table(["Month", "Contributions"], rows))
        lines.append("")


def _render_pull_requests(lines: list[str], analysis: PullRequestAnalysis) -> None:
    lines.append("### Pull requests")
    lines.append("")
    _render_properties(lines, analysis.metrics, _PULL_REQUEST_PROPERTIES)
    if analysis.per_repo_counts:
        rows = [[name, str(count)] for name, count in analysis.per_repo_counts.items()]
        lines.extend(_table(["Repository", "Pull requests"], rows))
        lines.append("")


def _render_issues(lines: list[str], analysis: IssueParticipationAnalysis) -> None:
    lines.append("### Issues")
    lines.append("")
    _render_properties(lines, analysis.metrics, _ISSUES_PROPERTIES)
    months = sorted({*analysis.monthly_opened, *analysis.monthly_closed})
    if months:
        rows = [
            [
                month,
                str(analysis.monthly_opened.get(month, 0)),
                str(analysis.monthly_closed.get(month, 0)),
            ]
            for month in months
        ]
        lines.extend(_table(["Month", "Opened", "Closed"], rows))
        lines.append("")


def _render_languages(lines: list[str], analysis: LanguageDistributionAnalysis) -> None:
    lines.append("### Languages")
    lines.append("")
    _render_properties(lines, analysis.metrics, _LANGUAGES_PROPERTIES)
    if analysis.distribution:
        rows = [
            [share.language, _fmt_bytes(share.bytes), _pct(share.share)]
            for share in analysis.distribution
        ]
        lines.extend(_table(["Language", "Bytes", "Share"], rows))
        lines.append("")


def _render_technology(lines: list[str], analysis: TechnologyDiversityAnalysis) -> None:
    lines.append("### Technology")
    lines.append("")
    _render_properties(lines, analysis.metrics, _TECHNOLOGY_PROPERTIES)
    if analysis.domain_shares:
        rows = [
            [share.domain, _fmt_bytes(share.bytes), _pct(share.share)]
            for share in analysis.domain_shares
        ]
        lines.extend(_table(["Domain", "Bytes", "Share"], rows))
        lines.append("")


def _render_analyses(lines: list[str], analyses: ProfileAnalyses | None) -> None:
    if analyses is None:
        return
    lines.append("## Analyses")
    lines.append("")
    if analyses.presence is not None:
        _render_presence(lines, analyses.presence)
    if analyses.readme is not None:
        _render_readme(lines, analyses.readme)
    if analyses.repository_quality is not None:
        _render_repository_quality(lines, analyses.repository_quality)
    if analyses.repository_activity is not None:
        _render_repository_activity(lines, analyses.repository_activity)
    if analyses.portfolio is not None:
        _render_portfolio(lines, analyses.portfolio)
    if analyses.stars is not None:
        _render_stars(lines, analyses.stars)
    if analyses.star_growth is not None:
        _render_star_growth(lines, analyses.star_growth)
    if analyses.network is not None:
        _render_network(lines, analyses.network)
    if analyses.commits is not None:
        _render_commits(lines, analyses.commits)
    if analyses.contribution_calendar is not None:
        _render_calendar(lines, analyses.contribution_calendar)
    if analyses.pull_requests is not None:
        _render_pull_requests(lines, analyses.pull_requests)
    if analyses.issues is not None:
        _render_issues(lines, analyses.issues)
    if analyses.languages is not None:
        _render_languages(lines, analyses.languages)
    if analyses.technology is not None:
        _render_technology(lines, analyses.technology)


def _render_metrics(lines: list[str], metrics: list[MetricRecord]) -> None:
    if not metrics:
        return
    lines.append("## Metrics")
    lines.append("")
    rows = []
    for metric in metrics:
        source = _source_text(metric.sources[0]) if metric.sources else "—"
        rows.append(
            [metric.id, metric.label, _metric_value(metric.value), _pct(metric.confidence), source]
        )
    lines.extend(_table(["Metric", "Label", "Value", "Confidence", "Source"], rows))
    lines.append("")


def render_markdown(report: Report) -> str:
    """Render ``report`` as complete GitHub-flavored Markdown."""
    lines: list[str] = []
    lines.append(f"# GitHub Profile Report: {report.profile.username}")
    lines.append("")
    lines.append(
        f"_ghdtk {report.tool_version} · generated {_format_datetime(report.generated_at)} · "
        f"analyzed {_format_datetime(report.profile.analyzed_at)}_"
    )
    lines.append("")
    _render_overall(lines, report.profile.overall)
    _render_dimension_scores(lines, report.profile.scores)
    _render_synthesis(lines, report.profile.synthesis)
    _render_findings(lines, report.profile.findings)
    _render_recommendations(lines, report.profile.recommendations)
    _render_analyses(lines, report.profile.analyses)
    _render_metrics(lines, report.profile.metrics)
    return "\n".join(lines).rstrip() + "\n"


def write_markdown(report: Report, path: str | Path) -> Path:
    """Render ``report`` to Markdown and write it to ``path``."""
    target = Path(path)
    target.write_text(render_markdown(report), encoding="utf-8")
    return target


__all__ = ["render_markdown", "write_markdown"]
