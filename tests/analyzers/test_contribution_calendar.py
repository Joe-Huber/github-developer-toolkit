"""Tests for contribution calendar analysis (issue #39)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from ghdtk.analyzers.contribution_calendar import (
    ContributionCalendarAnalysis,
    assess_contribution_calendar,
)
from ghdtk.analyzers.thresholds import AnalysisThresholds
from ghdtk.models.derived import FindingSeverity, MetricAvailability, MetricValue
from ghdtk.models.raw import (
    ContributionCalendar,
    ContributionDay,
    ContributionWeek,
    ProfileSnapshot,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _calendar(
    *,
    days: list[tuple[str, int]],
    total: int | None = None,
    restricted: int | None = None,
) -> ContributionCalendar:
    week = ContributionWeek(
        first_day=date.fromisoformat(days[0][0]),
        contribution_days=[
            ContributionDay(contribution_count=count, date=date.fromisoformat(day))
            for day, count in days
        ],
    )
    return ContributionCalendar(
        total_contributions=total,
        weeks=[week],
        restricted_contributions_count=restricted,
    )


def _snapshot(calendar: ContributionCalendar | None) -> ProfileSnapshot:
    return ProfileSnapshot(username="octocat", collected_at=NOW, contribution_calendar=calendar)


def _metric(result: ContributionCalendarAnalysis, metric_id: str) -> MetricValue:
    return next(metric.value for metric in result.metrics if metric.id == metric_id)


def _availability(result: ContributionCalendarAnalysis, metric_id: str) -> MetricAvailability:
    return next(metric.availability for metric in result.metrics if metric.id == metric_id)


def _days(*specs: tuple[str, int]) -> list[tuple[str, int]]:
    return list(specs)


def test_totals_active_days_and_density() -> None:
    days = _days(
        ("2024-01-01", 0),
        ("2024-01-02", 3),
        ("2024-01-03", 4),
        ("2024-01-04", 0),
        ("2024-01-05", 7),
        ("2024-01-06", 9),
        ("2024-01-07", 0),
        ("2024-01-08", 0),
        ("2024-01-09", 2),
        ("2024-01-10", 1),
        ("2024-01-11", 0),
        ("2024-01-12", 3),
        ("2024-01-13", 0),
        ("2024-01-14", 0),
    )
    result = assess_contribution_calendar(_snapshot(_calendar(days=days, total=29)))

    assert result.total_contributions == 29
    assert result.total_days == 14
    assert result.active_days == 7
    assert result.density == 0.5
    assert _metric(result, "contribution_calendar.total_contributions") == 29
    assert _metric(result, "contribution_calendar.active_days") == 7
    assert _metric(result, "contribution_calendar.density") == 0.5
    assert not any(finding.id == "contribution_calendar.no_activity" for finding in result.findings)


def test_streaks_and_gaps() -> None:
    days = _days(
        ("2024-01-01", 1),
        ("2024-01-02", 1),
        ("2024-01-03", 1),
        ("2024-01-04", 0),
        ("2024-01-05", 0),
        ("2024-01-06", 1),
        ("2024-01-07", 1),
        ("2024-01-08", 1),
        ("2024-01-09", 1),
        ("2024-01-10", 1),
        ("2024-01-11", 0),
        ("2024-01-12", 0),
        ("2024-01-13", 0),
        ("2024-01-14", 0),
    )
    result = assess_contribution_calendar(_snapshot(_calendar(days=days, total=8)))

    assert result.current_streak == 0
    assert result.longest_streak == 5
    assert result.longest_gap_days == 4
    assert _metric(result, "contribution_calendar.current_streak") == 0
    assert _metric(result, "contribution_calendar.longest_streak") == 5
    assert _metric(result, "contribution_calendar.longest_gap_days") == 4
    assert not any(
        finding.id == "contribution_calendar.notable_streak" for finding in result.findings
    )


def test_no_activity() -> None:
    days = _days(
        ("2024-01-01", 0),
        ("2024-01-02", 0),
        ("2024-01-03", 0),
        ("2024-01-04", 0),
        ("2024-01-05", 0),
    )
    result = assess_contribution_calendar(_snapshot(_calendar(days=days, total=0)))

    assert result.total_contributions == 0
    assert result.active_days == 0
    assert result.longest_gap_days == 5
    finding = next(f for f in result.findings if f.id == "contribution_calendar.no_activity")
    assert finding.severity is FindingSeverity.INFO
    assert "no contributions across 5 days" in finding.message


def test_single_active_day() -> None:
    days = _days(
        ("2024-01-01", 0),
        ("2024-01-02", 0),
        ("2024-01-03", 5),
        ("2024-01-04", 0),
        ("2024-01-05", 0),
    )
    result = assess_contribution_calendar(_snapshot(_calendar(days=days)))

    assert result.active_days == 1
    assert result.current_streak == 0
    assert result.longest_streak == 1
    assert result.longest_gap_days == 2
    assert _metric(result, "contribution_calendar.density") == 0.2


def test_private_contributions_disclosed() -> None:
    days = _days(("2024-01-01", 4), ("2024-01-02", 6))
    result = assess_contribution_calendar(_snapshot(_calendar(days=days, total=10, restricted=12)))

    assert result.restricted_contributions == 12
    assert _metric(result, "contribution_calendar.restricted_contributions") == 12
    finding = next(
        f for f in result.findings if f.id == "contribution_calendar.private_contributions"
    )
    assert finding.severity is FindingSeverity.INFO
    assert "12 contributions are restricted/private" in finding.message


def test_notable_streak_finding() -> None:
    days = _days(*[(f"2024-01-{i:02d}", 1) for i in range(1, 11)])
    result = assess_contribution_calendar(_snapshot(_calendar(days=days)))

    assert result.longest_streak == 10
    assert result.current_streak == 10
    finding = next(f for f in result.findings if f.id == "contribution_calendar.notable_streak")
    assert finding.severity is FindingSeverity.INFO
    assert "10-day contribution streak" in finding.title


def test_streak_threshold_is_config_driven() -> None:
    days = _days(*[(f"2024-01-{i:02d}", 1) for i in range(1, 6)])
    default = assess_contribution_calendar(_snapshot(_calendar(days=days)))
    assert not any(
        finding.id == "contribution_calendar.notable_streak" for finding in default.findings
    )

    relaxed = assess_contribution_calendar(
        _snapshot(_calendar(days=days)),
        thresholds=AnalysisThresholds(streak_notable_days=4),
    )
    assert any(finding.id == "contribution_calendar.notable_streak" for finding in relaxed.findings)


def _long_gap_days() -> list[tuple[str, int]]:
    start = date(2024, 1, 1)
    return [(start.isoformat(), 1)] + [
        ((start + timedelta(days=offset)).isoformat(), 0) for offset in range(1, 65)
    ]


def test_long_gap_finding() -> None:
    result = assess_contribution_calendar(_snapshot(_calendar(days=_long_gap_days())))

    assert result.longest_gap_days == 64
    finding = next(f for f in result.findings if f.id == "contribution_calendar.long_gap")
    assert finding.severity is FindingSeverity.LOW


def test_long_gap_threshold_is_config_driven() -> None:
    default = assess_contribution_calendar(_snapshot(_calendar(days=_long_gap_days())))
    assert any(finding.id == "contribution_calendar.long_gap" for finding in default.findings)

    relaxed = assess_contribution_calendar(
        _snapshot(_calendar(days=_long_gap_days())),
        thresholds=AnalysisThresholds(contribution_gap_days=100),
    )
    assert not any(finding.id == "contribution_calendar.long_gap" for finding in relaxed.findings)


def test_monthly_and_yearly_patterns() -> None:
    days = _days(
        ("2024-01-01", 3),
        ("2024-01-02", 2),
        ("2024-02-01", 5),
        ("2025-01-01", 4),
    )
    result = assess_contribution_calendar(_snapshot(_calendar(days=days)))

    assert result.monthly_pattern == {"2024-01": 5, "2024-02": 5, "2025-01": 4}
    assert result.yearly_pattern == {"2024": 10, "2025": 4}
    assert _metric(result, "contribution_calendar.month.2024-01") == 5
    assert _metric(result, "contribution_calendar.year.2025") == 4


def test_total_falls_back_to_observed_sum() -> None:
    days = _days(("2024-01-01", 3), ("2024-01-02", 4))
    result = assess_contribution_calendar(_snapshot(_calendar(days=days, total=None)))

    assert result.total_contributions == 7
    assert _metric(result, "contribution_calendar.total_contributions") == 7


def test_unavailable_calendar() -> None:
    result = assess_contribution_calendar(_snapshot(None))

    assert result.total_contributions is None
    assert _metric(result, "contribution_calendar.total_contributions") is None
    assert _metric(result, "contribution_calendar.restricted_contributions") is None
    assert (
        _availability(result, "contribution_calendar.total_contributions")
        is MetricAvailability.UNAVAILABLE
    )
    assert (
        _availability(result, "contribution_calendar.restricted_contributions")
        is MetricAvailability.UNAVAILABLE
    )
    finding = next(f for f in result.findings if f.id == "contribution_calendar.unavailable")
    assert finding.severity is FindingSeverity.INFO
    assert "was not collected" in finding.message
