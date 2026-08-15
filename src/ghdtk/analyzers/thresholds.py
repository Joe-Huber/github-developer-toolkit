"""Configurable analysis thresholds.

The repository analyzers (issues #29/#30/#31) accept an
:class:`AnalysisThresholds` so thresholds are config-driven rather than
hard-coded. Defaults mirror the ``analysis_*`` keys in :class:`Settings`
(issue #13) where they exist; the pipeline wires them from the config system,
and tests override them directly. Every threshold used by a finding or a
standout/concentration decision is documented next to its field.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["AnalysisThresholds"]


class AnalysisThresholds(BaseModel):
    """Documented thresholds shared by the repository analyzers.

    Frozen and validated: weights are bounded where meaningful so an
    impossible configuration cannot silently distort analysis.
    """

    model_config = ConfigDict(frozen=True)

    #: A repository is "stale" when its last push is older than this.
    staleness_days: int = Field(default=90, ge=1)

    #: Repositories with fewer stars are excluded from portfolio aggregate
    #: metrics (mirrors ``analysis_minimum_stars``).
    minimum_stars: int = Field(default=10, ge=0)

    #: Below this many repositories, concentration findings are skipped.
    minimum_repositories: int = Field(default=3, ge=0)

    #: A README shorter than this many characters is flagged as thin.
    readme_min_chars: int = Field(default=100, ge=0)

    #: A repository must reach this many stars to be a standout candidate.
    standout_star_threshold: int = Field(default=100, ge=1)

    #: A standout must have been pushed within this many days.
    standout_active_days: int = Field(default=90, ge=1)

    #: The top-1 repository share (of total stars) at or above which the
    #: portfolio is considered star-concentrated.
    concentration_top_share: float = Field(default=0.5, ge=0.0, le=1.0)

    #: The fork share at or above which a portfolio is heavily forked.
    fork_ratio_threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    #: Portfolio quality coverage (e.g. share of repos with a description)
    #: below which a coverage finding is raised.
    quality_coverage_threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    #: The recent growth window (days) used for star growth velocity.
    growth_window_days: int = Field(default=90, ge=1)

    #: recent/overall velocity at or above which star growth is "rising".
    trend_rising_ratio: float = Field(default=1.5, ge=1.0)

    #: recent/overall velocity at or below which star growth is "slowing".
    trend_slowing_ratio: float = Field(default=0.5, ge=0.0, le=1.0)

    #: follower/following ratio at or above which a profile is
    #: audience-driven, and the reciprocal at or below which it is
    #: network-driven.
    network_lopsided_ratio: float = Field(default=3.0, ge=1.0)

    @classmethod
    def from_settings(cls, settings: object) -> AnalysisThresholds:
        """Build thresholds from a settings object's ``analysis_*`` fields.

        ``settings`` is duck-typed so the analyzer layer does not import the
        config system directly: fields are read with ``getattr`` and only when
        present, leaving every other threshold at its default.
        """
        names = (
            "analysis_staleness_days",
            "analysis_minimum_stars",
            "analysis_minimum_repositories",
            "analysis_readme_min_chars",
        )
        values: dict[str, int] = {}
        for name in names:
            value = getattr(settings, name, None)
            if value is not None:
                values[name.replace("analysis_", "")] = int(value)
        return cls(**values)
