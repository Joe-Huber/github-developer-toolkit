"""Profile synthesis (issue #53).

Assembles the full assessment into the sections a report renders: strengths
from high dimension scores and standout findings, weaknesses from low scores
and quality issues, red flags for missing or possibly misleading information,
and a prioritized, actionable plan.

Ordering is fully deterministic so the same inputs always produce the same
synthesis:

- strengths/weaknesses start with the dimension-level lists from the overall
  score, followed by finding titles (standouts by id, quality issues by
  severity then id);
- red flags sort by severity (most severe first) then id;
- the plan sorts by priority (impact) first, then by effort (low-effort quick
  wins first), then by recommendation id.
"""

from __future__ import annotations

from collections.abc import Sequence

from ghdtk.models.derived import (
    Finding,
    FindingSeverity,
    OverallScore,
    Recommendation,
    Synthesis,
)
from ghdtk.recommendations.engine import order_key
from ghdtk.recommendations.rules import DISCLOSURE_PREFIXES

_RED_FLAG_TYPES = frozenset({"missing_information", "placeholder_value"})

_SEVERITY_RANK = {
    FindingSeverity.CRITICAL: 0,
    FindingSeverity.HIGH: 1,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.LOW: 3,
    FindingSeverity.INFO: 4,
}


def synthesize(
    *,
    findings: Sequence[Finding],
    overall: OverallScore | None = None,
    recommendations: Sequence[Recommendation] = (),
) -> Synthesis:
    """Assemble the assessment into strengths, weaknesses, red flags and a plan."""
    return Synthesis(
        strengths=_strengths(findings, overall),
        weaknesses=_weaknesses(findings, overall),
        red_flags=_red_flags(findings),
        plan=sorted(recommendations, key=order_key),
    )


def _strengths(findings: Sequence[Finding], overall: OverallScore | None) -> list[str]:
    dimension_strengths = list(overall.strengths) if overall is not None else []
    standouts = sorted(
        (finding.title for finding in findings if finding.type == "standout"),
    )
    return dimension_strengths + standouts


def _weaknesses(findings: Sequence[Finding], overall: OverallScore | None) -> list[str]:
    dimension_weaknesses = list(overall.weaknesses) if overall is not None else []
    issues = sorted(
        (finding for finding in findings if finding.type == "quality_issue"),
        key=lambda f: (_SEVERITY_RANK[f.severity], f.id),
    )
    return dimension_weaknesses + [finding.title for finding in issues]


def _red_flags(findings: Sequence[Finding]) -> list[str]:
    return [
        finding.title
        for finding in sorted(findings, key=lambda f: (_SEVERITY_RANK[f.severity], f.id))
        if _is_red_flag(finding)
    ]


def _is_red_flag(finding: Finding) -> bool:
    if finding.type in _RED_FLAG_TYPES:
        return True
    return any(
        finding.id == prefix or finding.id.startswith(prefix) for prefix in DISCLOSURE_PREFIXES
    )
