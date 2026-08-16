"""Dimension scorers for the scoring engine (issues #48/#49)."""

from __future__ import annotations

from ghdtk.scoring.framework import ScoringConfig
from ghdtk.scoring.scorers.activity import ActivityScorer
from ghdtk.scoring.scorers.base import BaseScorer
from ghdtk.scoring.scorers.community import CommunityScorer
from ghdtk.scoring.scorers.consistency import ConsistencyScorer
from ghdtk.scoring.scorers.contribution import ContributionScorer
from ghdtk.scoring.scorers.open_source import OpenSourceScorer
from ghdtk.scoring.scorers.profile import ProfileScorer
from ghdtk.scoring.scorers.repository import RepositoryScorer
from ghdtk.scoring.scorers.visibility import VisibilityScorer

__all__ = [
    "ActivityScorer",
    "BaseScorer",
    "CommunityScorer",
    "ConsistencyScorer",
    "ContributionScorer",
    "OpenSourceScorer",
    "ProfileScorer",
    "RepositoryScorer",
    "VisibilityScorer",
    "default_scorers",
]


def default_scorers(config: ScoringConfig | None = None) -> tuple[BaseScorer, ...]:
    """The eight standard dimension scorers in aggregation order."""
    return (
        ProfileScorer(config),
        RepositoryScorer(config),
        ConsistencyScorer(config),
        ActivityScorer(config),
        ContributionScorer(config),
        CommunityScorer(config),
        OpenSourceScorer(config),
        VisibilityScorer(config),
    )
