"""Complete set of derived analyzer outputs for one profile (issue #55).

``ProfileAnalyses`` carries every analyzer result produced for a profile in a
fixed, documented field order. Fields are ``None`` when the corresponding
analysis did not run or produced nothing, so the assembled report stays honest
about missing data and round-trips to JSON losslessly.

The analyzer output types are referenced lazily (string annotations resolved by
:func:`ensure_built`) to keep the derived layer importable from the analyzers:
the analyzers depend on the derived models, so the derived layer never imports
the analyzers eagerly. ``ensure_built`` is invoked by the report assembler and
by :mod:`ghdtk.models.derived` after both layers finish loading.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from ghdtk.analyzers.commits import CommitActivity
    from ghdtk.analyzers.contribution_calendar import ContributionCalendarAnalysis
    from ghdtk.analyzers.issues import IssueParticipationAnalysis
    from ghdtk.analyzers.languages import LanguageDistributionAnalysis
    from ghdtk.analyzers.network import FollowerNetwork
    from ghdtk.analyzers.portfolio import PortfolioComposition
    from ghdtk.analyzers.presence import ProfilePresence
    from ghdtk.analyzers.pull_requests import PullRequestAnalysis
    from ghdtk.analyzers.readme import ReadmeAssessment
    from ghdtk.analyzers.repository_activity import RepositoryActivity
    from ghdtk.analyzers.repository_quality import RepositoryQuality
    from ghdtk.analyzers.star_growth import StarGrowthAnalysis
    from ghdtk.analyzers.stars import StarsAnalysis
    from ghdtk.analyzers.technology import TechnologyDiversityAnalysis

__all__ = ["ProfileAnalyses", "ensure_built"]


class ProfileAnalyses(BaseModel):
    """All derived analyzer outputs for one profile.

    Fields are ``None`` when the corresponding analysis was not run. The field
    order is the canonical section order used by the report renderers.
    """

    model_config = ConfigDict(frozen=True, defer_build=True)

    presence: ProfilePresence | None = None
    readme: ReadmeAssessment | None = None
    repository_quality: RepositoryQuality | None = None
    repository_activity: RepositoryActivity | None = None
    portfolio: PortfolioComposition | None = None
    stars: StarsAnalysis | None = None
    star_growth: StarGrowthAnalysis | None = None
    network: FollowerNetwork | None = None
    commits: CommitActivity | None = None
    contribution_calendar: ContributionCalendarAnalysis | None = None
    pull_requests: PullRequestAnalysis | None = None
    issues: IssueParticipationAnalysis | None = None
    languages: LanguageDistributionAnalysis | None = None
    technology: TechnologyDiversityAnalysis | None = None


_ANALYSIS_TYPES: dict[str, type] | None = None


def ensure_built() -> None:
    """Resolve the analyzer output types and build :class:`ProfileAnalyses`.

    Idempotent; safe to call repeatedly. Raises ``ImportError`` while the
    analyzers are still loading (the derived layer is imported from within the
    analyzers), in which case the caller defers and retries once the analyzers
    finish loading.
    """
    global _ANALYSIS_TYPES
    if _ANALYSIS_TYPES is not None:
        return
    from ghdtk.analyzers.commits import CommitActivity
    from ghdtk.analyzers.contribution_calendar import ContributionCalendarAnalysis
    from ghdtk.analyzers.issues import IssueParticipationAnalysis
    from ghdtk.analyzers.languages import LanguageDistributionAnalysis
    from ghdtk.analyzers.network import FollowerNetwork
    from ghdtk.analyzers.portfolio import PortfolioComposition
    from ghdtk.analyzers.presence import ProfilePresence
    from ghdtk.analyzers.pull_requests import PullRequestAnalysis
    from ghdtk.analyzers.readme import ReadmeAssessment
    from ghdtk.analyzers.repository_activity import RepositoryActivity
    from ghdtk.analyzers.repository_quality import RepositoryQuality
    from ghdtk.analyzers.star_growth import StarGrowthAnalysis
    from ghdtk.analyzers.stars import StarsAnalysis
    from ghdtk.analyzers.technology import TechnologyDiversityAnalysis

    _ANALYSIS_TYPES = {
        "CommitActivity": CommitActivity,
        "ContributionCalendarAnalysis": ContributionCalendarAnalysis,
        "FollowerNetwork": FollowerNetwork,
        "IssueParticipationAnalysis": IssueParticipationAnalysis,
        "LanguageDistributionAnalysis": LanguageDistributionAnalysis,
        "PortfolioComposition": PortfolioComposition,
        "ProfilePresence": ProfilePresence,
        "PullRequestAnalysis": PullRequestAnalysis,
        "ReadmeAssessment": ReadmeAssessment,
        "RepositoryActivity": RepositoryActivity,
        "RepositoryQuality": RepositoryQuality,
        "StarGrowthAnalysis": StarGrowthAnalysis,
        "StarsAnalysis": StarsAnalysis,
        "TechnologyDiversityAnalysis": TechnologyDiversityAnalysis,
    }
    ProfileAnalyses.model_rebuild(_types_namespace=_ANALYSIS_TYPES)
