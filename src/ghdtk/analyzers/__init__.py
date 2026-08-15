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
"""

from __future__ import annotations

from ghdtk.analyzers.heuristics import find_boilerplate, find_placeholders
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
from ghdtk.analyzers.stars import StarsAnalysis, StarsRankingEntry, assess_star_distribution
from ghdtk.analyzers.thresholds import AnalysisThresholds

__all__ = [
    "AnalysisThresholds",
    "FieldAssessment",
    "FieldStatus",
    "PortfolioComposition",
    "ProfilePresence",
    "ReadmeAssessment",
    "ReadmeState",
    "RepositoryActivity",
    "RepositoryActivitySignals",
    "RepositoryCompositionSignals",
    "RepositoryQuality",
    "RepositoryQualitySignals",
    "StarsAnalysis",
    "StarsRankingEntry",
    "assess_portfolio_composition",
    "assess_profile_presence",
    "assess_readme_quality",
    "assess_repository_activity",
    "assess_repository_quality",
    "assess_star_distribution",
    "find_boilerplate",
    "find_placeholders",
]
