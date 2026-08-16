"""Derived analysis data models.

Structured, reproducible, explainable analysis output — clearly separated from
raw data. Every metric, score component, finding and recommendation carries
provenance (:class:`SourceReference`) pointing at the raw inputs that produced
it, and the whole analysis serializes to JSON losslessly.
"""

from __future__ import annotations

from ghdtk.models.derived.analysis import ProfileAnalysis, Report
from ghdtk.models.derived.finding import Finding, FindingSeverity
from ghdtk.models.derived.metric import MetricRecord, MetricValue
from ghdtk.models.derived.provenance import SourceEntityKind, SourceReference
from ghdtk.models.derived.recommendation import (
    Recommendation,
    RecommendationEffort,
    RecommendationPriority,
)
from ghdtk.models.derived.score import (
    DimensionContribution,
    DimensionId,
    DimensionScore,
    OverallScore,
    ScoreBreakdown,
)
from ghdtk.models.derived.synthesis import Synthesis

__all__ = [
    "DimensionContribution",
    "DimensionId",
    "DimensionScore",
    "Finding",
    "FindingSeverity",
    "MetricRecord",
    "MetricValue",
    "OverallScore",
    "ProfileAnalysis",
    "Recommendation",
    "RecommendationEffort",
    "RecommendationPriority",
    "Report",
    "ScoreBreakdown",
    "SourceEntityKind",
    "SourceReference",
    "Synthesis",
]
