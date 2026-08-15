"""Profile analyzers.

Consume raw snapshots and produce derived :mod:`ghdtk.models.derived` metrics
and findings. Every derived value references the raw inputs that produced it
so analysis stays reproducible and explainable.

Implemented analyzers:

- :func:`assess_profile_presence` — profile metadata & presentation analysis
  (issue #24).
- :func:`assess_readme_quality` — README quality & structure analysis
  (issue #26).
"""

from __future__ import annotations

from ghdtk.analyzers.heuristics import find_boilerplate, find_placeholders
from ghdtk.analyzers.presence import (
    FieldAssessment,
    FieldStatus,
    ProfilePresence,
    assess_profile_presence,
)

__all__ = [
    "FieldAssessment",
    "FieldStatus",
    "ProfilePresence",
    "assess_profile_presence",
    "find_boilerplate",
    "find_placeholders",
]
