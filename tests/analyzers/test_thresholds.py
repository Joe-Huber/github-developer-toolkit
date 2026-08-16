"""Unit tests for the configurable analysis thresholds (issue #60).

Covers the documented defaults, the bounded/frozen validation, and the
duck-typed ``from_settings`` constructor that maps ``analysis_*`` config keys.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ghdtk.analyzers.thresholds import AnalysisThresholds


def test_defaults_match_documented_analysis_config() -> None:
    thresholds = AnalysisThresholds()
    assert thresholds.staleness_days == 90
    assert thresholds.minimum_stars == 10
    assert thresholds.minimum_repositories == 3
    assert thresholds.readme_min_chars == 100
    assert thresholds.standout_star_threshold == 100
    assert thresholds.standout_active_days == 90
    assert thresholds.concentration_top_share == 0.5
    assert thresholds.fork_ratio_threshold == 0.5
    assert thresholds.quality_coverage_threshold == 0.5
    assert thresholds.growth_window_days == 90
    assert thresholds.trend_rising_ratio == 1.5
    assert thresholds.trend_slowing_ratio == 0.5
    assert thresholds.network_lopsided_ratio == 3.0
    assert thresholds.commit_gap_days == 60
    assert thresholds.commit_cadence_per_month == 4.0
    assert thresholds.contribution_gap_days == 60
    assert thresholds.streak_notable_days == 7
    assert thresholds.pr_external_share == 0.5
    assert thresholds.pr_reviewed_share == 0.3
    assert thresholds.issue_external_share == 0.5
    assert thresholds.issue_commented_share == 0.5
    assert thresholds.issue_trend_min_months == 2
    assert thresholds.issue_trend_min_issues == 4
    assert thresholds.language_concentration_threshold == 0.6
    assert thresholds.language_distinct_threshold == 5
    assert thresholds.technology_mapping_coverage_threshold == 0.5
    assert thresholds.technology_specialization_threshold == 0.5
    assert thresholds.technology_diversity_threshold == 0.5


def test_overrides_are_accepted() -> None:
    thresholds = AnalysisThresholds(staleness_days=30, concentration_top_share=0.9)
    assert thresholds.staleness_days == 30
    assert thresholds.concentration_top_share == 0.9
    assert thresholds.minimum_stars == 10


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"staleness_days": 0}, "greater than or equal to 1"),
        ({"concentration_top_share": 1.5}, "less than or equal to 1"),
        ({"fork_ratio_threshold": -0.1}, "greater than or equal to 0"),
        ({"trend_rising_ratio": 0.5}, "greater than or equal to 1"),
        ({"issue_trend_min_months": 1}, "greater than or equal to 2"),
    ],
)
def test_invalid_config_is_rejected(overrides: dict[str, object], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        AnalysisThresholds(**overrides)


def test_from_settings_maps_analysis_keys() -> None:
    class SettingsLike:
        analysis_staleness_days = 30
        analysis_minimum_stars = 20
        analysis_minimum_repositories = 5
        analysis_readme_min_chars = 250
        unrelated_field = "ignored"

    thresholds = AnalysisThresholds.from_settings(SettingsLike())
    assert thresholds.staleness_days == 30
    assert thresholds.minimum_stars == 20
    assert thresholds.minimum_repositories == 5
    assert thresholds.readme_min_chars == 250
    assert thresholds.growth_window_days == 90


def test_from_settings_without_keys_uses_defaults() -> None:
    class EmptySettings:
        pass

    thresholds = AnalysisThresholds.from_settings(EmptySettings())
    assert thresholds.staleness_days == 90
    assert thresholds.minimum_stars == 10


def test_from_settings_coerces_string_values() -> None:
    class StringySettings:
        analysis_staleness_days = "45"

    thresholds = AnalysisThresholds.from_settings(StringySettings())
    assert thresholds.staleness_days == 45
