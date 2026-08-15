"""Dimension scorers for the scoring engine (issues #48/#49)."""

from __future__ import annotations

from ghdtk.scoring.framework import ScoringConfig
from ghdtk.scoring.scorers.base import BaseScorer
from ghdtk.scoring.scorers.consistency import ConsistencyScorer
from ghdtk.scoring.scorers.profile import ProfileScorer
from ghdtk.scoring.scorers.repository import RepositoryScorer

__all__ = [
    "BaseScorer",
    "ConsistencyScorer",
    "ProfileScorer",
    "RepositoryScorer",
    "default_scorers",
]


def default_scorers(config: ScoringConfig | None = None) -> tuple[BaseScorer, ...]:
    """The standard dimension scorers in aggregation order."""
    return (
        ProfileScorer(config),
        RepositoryScorer(config),
        ConsistencyScorer(config),
    )
