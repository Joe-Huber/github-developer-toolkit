"""Scoring engine.

Combines derived metrics into weighted dimension scores with a transparent
breakdown so every score can be explained from its inputs.

Implemented layers:

- :mod:`~ghdtk.scoring.framework` — scorer interface, ``ScoreInputs``,
  configurable ``ScoringConfig`` and the ``ScoringRegistry`` (issue #47).
- :mod:`~ghdtk.scoring.normalize` — normalization helpers and component
  blending (issue #47).
- :mod:`~ghdtk.scoring.scorers` — the eight dimension scorers
  (issues #48/#49).
- :mod:`~ghdtk.scoring.aggregate` — overall score aggregation and
  explainability (issue #50).
"""

from __future__ import annotations

from ghdtk.scoring.framework import (
    DIMENSION_LABELS,
    AnalysisWithMetrics,
    ScoreInputs,
    Scorer,
    ScoringConfig,
    ScoringRegistry,
    dedupe_sources,
    default_weights,
    dimension_label,
    metric_sources,
    metric_value,
)
from ghdtk.scoring.normalize import (
    ScoredComponent,
    blend,
    clamp,
    normalize_linear,
    normalize_log,
    normalize_ratio,
)
from ghdtk.scoring.scorers import default_scorers

__all__ = [
    "DIMENSION_LABELS",
    "AnalysisWithMetrics",
    "ScoreInputs",
    "ScoredComponent",
    "Scorer",
    "ScoringConfig",
    "ScoringRegistry",
    "blend",
    "clamp",
    "dedupe_sources",
    "default_scorers",
    "default_weights",
    "dimension_label",
    "metric_sources",
    "metric_value",
    "normalize_linear",
    "normalize_log",
    "normalize_ratio",
]
