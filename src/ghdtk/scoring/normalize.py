"""Score normalization helpers.

Shared building blocks for dimension scorers: turn raw or derived values into
0-100 component scores with documented, configurable behavior, and blend
weighted components into a dimension score with a transparent breakdown.

Every helper defines its edge-case behavior explicitly (out-of-range values,
degenerate ranges, zero total weight) so scores never divide by zero or leak
``NaN`` into the derived output.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from ghdtk.models.derived.provenance import SourceReference
from ghdtk.models.derived.score import ScoreBreakdown


@dataclass(frozen=True)
class ScoredComponent:
    """One 0-100 component of a dimension score, ready to be blended."""

    component_id: str
    label: str
    value: float
    weight: float
    metric_id: str | None = None
    sources: tuple[SourceReference, ...] = ()


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Clamp ``value`` into ``[low, high]``."""
    return max(low, min(high, value))


def normalize_ratio(ratio: float, *, scale: float = 100.0) -> float:
    """Map a ``[0, 1]`` ratio onto ``[0, scale]``, clamping out-of-range input."""
    return clamp(ratio, 0.0, 1.0) * scale


def normalize_linear(
    value: float,
    low: float,
    high: float,
    *,
    high_is_good: bool = True,
) -> float:
    """Linearly map ``value`` in ``[low, high]`` to ``[0, 100]``.

    With ``high_is_good=False`` the mapping is inverted so ``low`` is the
    full-credit anchor. Out-of-range values are clamped; a degenerate
    ``low == high`` range grants full credit exactly at the single anchor.
    """
    if high == low:
        if high_is_good:
            return 100.0 if value >= high else 0.0
        return 100.0 if value <= low else 0.0
    ratio = (value - low) / (high - low)
    if not high_is_good:
        ratio = 1.0 - ratio
    return clamp(ratio * 100.0)


def normalize_log(
    value: float,
    low: float,
    high: float,
    *,
    high_is_good: bool = True,
    base: float = 10.0,
) -> float:
    """Logarithmically map ``value`` in ``[low, high]`` to ``[0, 100]``.

    Log scaling compresses large ranges so moving from 0 to 1000 counts like
    moving from 1000 to 10000. Requires ``0 < low < high``; values at or below
    ``low`` score zero and values at or above ``high`` score full credit.
    """
    if low <= 0 or high <= low:
        raise ValueError("normalize_log requires 0 < low < high")
    if value <= low:
        ratio = 0.0
    elif value >= high:
        ratio = 1.0
    else:
        log_v = math.log(value, base)
        log_l = math.log(low, base)
        log_h = math.log(high, base)
        ratio = (log_v - log_l) / (log_h - log_l)
    if not high_is_good:
        ratio = 1.0 - ratio
    return clamp(ratio * 100.0)


def blend(components: Sequence[ScoredComponent]) -> tuple[float, list[ScoreBreakdown]]:
    """Weighted-blend components into a 0-100 score with a transparent breakdown.

    The blended score is the weighted average of the component values. Each
    returned :class:`ScoreBreakdown` carries its normalized weight (the share
    of total weight) and its contribution (``value * normalized weight``), so
    the contributions sum to the blended score. With no positive weight the
    score is zero and the breakdown is empty.
    """
    total_weight = sum(component.weight for component in components)
    if total_weight <= 0:
        return 0.0, []
    score = sum(component.value * component.weight for component in components) / total_weight
    breakdown: list[ScoreBreakdown] = []
    for component in components:
        normalized_weight = component.weight / total_weight
        breakdown.append(
            ScoreBreakdown(
                component_id=component.component_id,
                label=component.label,
                weight=normalized_weight,
                contribution=component.value * normalized_weight,
                metric_id=component.metric_id,
                sources=list(component.sources),
            )
        )
    return score, breakdown
