"""Profile analyzers.

Consume raw snapshots and produce derived :mod:`ghdtk.models.derived` metrics
and findings. Every derived value references the raw inputs that produced it
so analysis stays reproducible and explainable.

Implemented analyzers:

- :func:`assess_profile_presence` — profile metadata & presentation analysis
  (issue #24).
- :func:`assess_repository_activity` — repository activity, age & consistency
  analysis (issue #30).
- :func:`assess_portfolio_composition` — portfolio composition & standout
  identification analysis (issue #31).
- :func:`assess_star_distribution` — stars aggregation & distribution analysis
  (issue #33).
- :func:`assess_star_growth` — star growth & trend analysis from the stargazer
  timeline (issue #34).
- :func:`assess_follower_network` — followers, ratio, reach & network analysis
  (issue #36).
- :func:`assess_commit_activity` — commit history & activity analysis
  (issue #38).
- :func:`assess_contribution_calendar` — contribution calendar consistency &
  streaks analysis (issue #39).
"""

from __future__ import annotations

from ghdtk.analyzers.commits import CommitActivity, assess_commit_activity
from ghdtk.analyzers.contribution_calendar import (
    ContributionCalendarAnalysis,
    assess_contribution_calendar,
)
from ghdtk.analyzers.heuristics import find_boilerplate, find_placeholders
from ghdtk.analyzers.network import FollowerNetwork, assess_follower_network
from ghdtk.analyzers.portfolio import (
    PortfolioComposition,
    RepositoryCompositionSignals,
    assess_portfolio_composition,
)
from ghdtk.analyzers.presence import (
    FieldAssessment,
    FieldStatus,
    ProfilePresence,
    assess_profile_presence,
)
from ghdtk.analyzers.readme import ReadmeAssessment, assess_readme_quality
from ghdtk.analyzers.repository_activity import (
    RepositoryActivity,
    RepositoryActivitySignals,
    assess_repository_activity,
)
from ghdtk.analyzers.repository_quality import (
    ReadmeState,
    RepositoryQuality,
    RepositoryQualitySignals,
    assess_repository_quality,
)
from ghdtk.analyzers.star_growth import (
    StarGrowthAnalysis,
    StarGrowthStatus,
    assess_star_growth,
)
from ghdtk.analyzers.stars import StarsAnalysis, StarsRankingEntry, assess_star_distribution
from ghdtk.analyzers.thresholds import AnalysisThresholds

__all__ = [
    "AnalysisThresholds",
    "CommitActivity",
    "ContributionCalendarAnalysis",
    "FieldAssessment",
    "FieldStatus",
    "FollowerNetwork",
    "PortfolioComposition",
    "ProfilePresence",
    "ReadmeAssessment",
    "ReadmeState",
    "RepositoryActivity",
    "RepositoryActivitySignals",
    "RepositoryCompositionSignals",
    "RepositoryQuality",
    "RepositoryQualitySignals",
    "StarGrowthAnalysis",
    "StarGrowthStatus",
    "StarsAnalysis",
    "StarsRankingEntry",
    "assess_commit_activity",
    "assess_contribution_calendar",
    "assess_follower_network",
    "assess_portfolio_composition",
    "assess_profile_presence",
    "assess_readme_quality",
    "assess_repository_activity",
    "assess_repository_quality",
    "assess_star_distribution",
    "assess_star_growth",
    "find_boilerplate",
    "find_placeholders",
]
