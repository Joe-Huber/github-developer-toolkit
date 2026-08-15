"""Contribution calendar consistency & streaks analysis (issue #39).

Quantifies the GitHub contribution graph: totals, active days, streaks, gaps,
activity density and yearly/monthly patterns, with honest handling of hidden
contributions.

Documented interpretation & availability rules:

- **The calendar is the GraphQL ``contributionCalendar``** collected for the
  profile (the documented fallback is: when the GraphQL collection fails or is
  absent, the analysis reports ``unavailable`` with a rationale rather than
  guessing).
- **Streaks are run-length counts over calendar days** in the returned window
  (approximately the last year). ``current_streak`` is the run of active days
  ending at the last day of the calendar window; ``longest_streak`` is the
  longest run anywhere in the window; ``longest_gap`` is the longest run of
  days with no contributions.
- **Hidden contributions are disclosed, never assumed.** ``restrictedContributionsCount``
  (private contributions made while private contributions are hidden) is
  fetched alongside the calendar and reported; a non-zero count produces a
  disclosure finding so the totals are understood as calendar-visible only.
- **Totals** prefer the calendar's ``totalContributions`` and fall back to the
  sum of the day counts only when the total is absent; per-month/per-year
  patterns sum the observed day counts.
"""

from __future__ import annotations

from collections import Counter
from datetime import date

from pydantic import BaseModel, ConfigDict

from ghdtk.analyzers.thresholds import AnalysisThresholds
from ghdtk.models.derived import (
    DimensionId,
    Finding,
    FindingSeverity,
    MetricRecord,
    SourceEntityKind,
    SourceReference,
)
from ghdtk.models.raw import ContributionCalendar, ProfileSnapshot

__all__ = ["ContributionCalendarAnalysis", "assess_contribution_calendar"]

_UNAVAILABLE = "unavailable"


def _source(username: str, field: str) -> SourceReference:
    return SourceReference(
        entity=SourceEntityKind.USER,
        identifier=username,
        field=field,
    )


class ContributionCalendarAnalysis(BaseModel):
    """The contribution calendar consistency & streaks assessment."""

    model_config = ConfigDict(frozen=True)

    username: str
    total_contributions: int | None = None
    active_days: int = 0
    total_days: int = 0
    density: float = 0.0
    current_streak: int = 0
    longest_streak: int = 0
    longest_gap_days: int = 0
    restricted_contributions: int | None = None
    monthly_pattern: dict[str, int]
    yearly_pattern: dict[str, int]
    metrics: list[MetricRecord]
    findings: list[Finding]


def _flat_days(calendar: ContributionCalendar) -> list[tuple[date, int]]:
    days: list[tuple[date, int]] = []
    for week in calendar.weeks or []:
        for day in week.contribution_days or []:
            if day.date is not None:
                days.append((day.date, day.contribution_count or 0))
    return sorted(days, key=lambda item: item[0])


def assess_contribution_calendar(
    snapshot: ProfileSnapshot,
    *,
    thresholds: AnalysisThresholds | None = None,
) -> ContributionCalendarAnalysis:
    """Assess totals, active days, streaks, gaps and density."""
    thresholds = thresholds or AnalysisThresholds()
    now_ts = snapshot.collected_at
    username = snapshot.username
    calendar = snapshot.contribution_calendar
    findings: list[Finding] = []
    sources = [_source(username, "contribution_calendar")]

    if calendar is None:
        findings.append(
            Finding(
                id="contribution_calendar.unavailable",
                type="informational",
                severity=FindingSeverity.INFO,
                title="Contribution calendar is unavailable",
                message=(
                    "The contribution calendar was not collected (GraphQL "
                    "collection failed or was skipped); calendar-based metrics "
                    "report unavailable."
                ),
                dimension=DimensionId.ACTIVITY,
                evidence=sources,
            )
        )
        return ContributionCalendarAnalysis(
            username=username,
            total_contributions=None,
            active_days=0,
            total_days=0,
            density=0.0,
            current_streak=0,
            longest_streak=0,
            longest_gap_days=0,
            restricted_contributions=None,
            monthly_pattern={},
            yearly_pattern={},
            metrics=[
                MetricRecord(
                    id="contribution_calendar.total_contributions",
                    label="Total contributions",
                    value=_UNAVAILABLE,
                    timestamp=now_ts,
                    sources=sources,
                ),
                MetricRecord(
                    id="contribution_calendar.restricted_contributions",
                    label="Hidden (private) contributions",
                    value=_UNAVAILABLE,
                    timestamp=now_ts,
                    sources=sources,
                ),
            ],
            findings=findings,
        )

    days = _flat_days(calendar)
    total_days = len(days)
    active_flags = [1 if count > 0 else 0 for _, count in days]
    active_days = sum(active_flags)
    density = _round(active_days / total_days) if total_days else 0.0

    observed_total = sum(count for _, count in days)
    total_contributions = (
        calendar.total_contributions if calendar.total_contributions is not None else observed_total
    )

    longest_streak = current = 0
    for flag in active_flags:
        if flag:
            current += 1
            longest_streak = max(longest_streak, current)
        else:
            current = 0
    current_streak = 0
    for flag in reversed(active_flags):
        if flag:
            current_streak += 1
        else:
            break
    longest_gap = zero_run = 0
    for flag in active_flags:
        if not flag:
            zero_run += 1
            longest_gap = max(longest_gap, zero_run)
        else:
            zero_run = 0

    monthly_pattern = Counter[str](f"{day.isoformat()[:7]}" for day, _ in days)
    yearly_pattern = Counter[str](f"{day.isoformat()[:4]}" for day, _ in days)
    monthly_totals: dict[str, int] = {key: 0 for key in sorted(monthly_pattern)}
    yearly_totals: dict[str, int] = {key: 0 for key in sorted(yearly_pattern)}
    for day, count in days:
        monthly_totals[f"{day.isoformat()[:7]}"] += count
        yearly_totals[f"{day.isoformat()[:4]}"] += count

    restricted = calendar.restricted_contributions_count
    if total_contributions == 0:
        findings.append(
            Finding(
                id="contribution_calendar.no_activity",
                type="informational",
                severity=FindingSeverity.INFO,
                title="No contributions in the calendar window",
                message=(
                    f"The contribution calendar shows no contributions across {total_days} days."
                ),
                dimension=DimensionId.ACTIVITY,
                evidence=sources,
            )
        )
    if restricted:
        findings.append(
            Finding(
                id="contribution_calendar.private_contributions",
                type="informational",
                severity=FindingSeverity.INFO,
                title="Some contributions are hidden",
                message=(
                    f"{restricted} contributions are restricted/private and hidden "
                    "from the calendar; the reported totals reflect only "
                    "calendar-visible contributions."
                ),
                dimension=DimensionId.ACTIVITY,
                evidence=[_source(username, "restricted_contributions_count")],
            )
        )
    if longest_streak >= thresholds.streak_notable_days:
        findings.append(
            Finding(
                id="contribution_calendar.notable_streak",
                type="standout",
                severity=FindingSeverity.INFO,
                title=f"{longest_streak}-day contribution streak",
                message=(
                    f"The longest run of active days in the calendar window is "
                    f"{longest_streak} days."
                ),
                dimension=DimensionId.ACTIVITY,
                evidence=sources,
            )
        )
    if longest_gap >= thresholds.contribution_gap_days:
        findings.append(
            Finding(
                id="contribution_calendar.long_gap",
                type="quality_issue",
                severity=FindingSeverity.LOW,
                title="Long gap in the contribution calendar",
                message=(
                    f"The longest run of days without contributions in the window "
                    f"was {longest_gap} days."
                ),
                dimension=DimensionId.ACTIVITY,
                evidence=sources,
            )
        )

    metrics = [
        MetricRecord(
            id="contribution_calendar.total_contributions",
            label="Total contributions",
            value=total_contributions,
            timestamp=now_ts,
            sources=sources,
        ),
        MetricRecord(
            id="contribution_calendar.active_days",
            label="Active days",
            value=active_days,
            timestamp=now_ts,
            sources=sources,
        ),
        MetricRecord(
            id="contribution_calendar.total_days",
            label="Days in the calendar window",
            value=total_days,
            timestamp=now_ts,
            sources=sources,
        ),
        MetricRecord(
            id="contribution_calendar.density",
            label="Activity density (active days / total days)",
            value=density,
            timestamp=now_ts,
            sources=sources,
        ),
        MetricRecord(
            id="contribution_calendar.current_streak",
            label="Current streak (active days ending the window)",
            value=current_streak,
            timestamp=now_ts,
            sources=sources,
        ),
        MetricRecord(
            id="contribution_calendar.longest_streak",
            label="Longest streak",
            value=longest_streak,
            timestamp=now_ts,
            sources=sources,
        ),
        MetricRecord(
            id="contribution_calendar.longest_gap_days",
            label="Longest run of inactive days",
            value=longest_gap,
            timestamp=now_ts,
            sources=sources,
        ),
        MetricRecord(
            id="contribution_calendar.restricted_contributions",
            label="Hidden (private) contributions",
            value=restricted if restricted is not None else _UNAVAILABLE,
            timestamp=now_ts,
            sources=[_source(username, "restricted_contributions_count")],
        ),
    ]
    for month, count in monthly_totals.items():
        metrics.append(
            MetricRecord(
                id=f"contribution_calendar.month.{month}",
                label=f"Contributions in {month}",
                value=count,
                timestamp=now_ts,
                sources=sources,
            )
        )
    for year, count in yearly_totals.items():
        metrics.append(
            MetricRecord(
                id=f"contribution_calendar.year.{year}",
                label=f"Contributions in {year}",
                value=count,
                timestamp=now_ts,
                sources=sources,
            )
        )

    return ContributionCalendarAnalysis(
        username=username,
        total_contributions=total_contributions,
        active_days=active_days,
        total_days=total_days,
        density=density,
        current_streak=current_streak,
        longest_streak=longest_streak,
        longest_gap_days=longest_gap,
        restricted_contributions=restricted,
        monthly_pattern=monthly_totals,
        yearly_pattern=yearly_totals,
        metrics=metrics,
        findings=findings,
    )


def _round(value: float, digits: int = 2) -> float:
    return round(value, digits)
