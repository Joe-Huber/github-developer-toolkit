"""Profile dimension scorer (issue #48).

Scores the ``presence`` dimension from the profile & README analysis (issue
#23): profile-presentation completeness (:mod:`~ghdtk.analyzers.presence`)
and profile-README quality (:mod:`~ghdtk.analyzers.readme`).

Documented formula (blended, 0-100):

- **Profile field completeness** (weight 1.0): the share of assessed fields
  (bio, website, location, ...) with status ``present``.
- **Profile README quality** (weight 1.0, only when a README was assessed):
  40% word-count component (linear up to 100 words), 35% structure component
  (mean of headings/code blocks/links/badges-or-images presence) and 25%
  personalization component (username mentions, capped at 50 when generic
  boilerplate wording is detected). A README that is missing, empty or failed
  to fetch scores zero.

Empty-data handling: with no presence analysis the dimension cannot be scored
and ``None`` is returned; a missing README assessment simply drops the README
component and re-normalizes the remaining weight.
"""

from __future__ import annotations

from ghdtk.analyzers.presence import FieldStatus, ProfilePresence
from ghdtk.analyzers.readme import ReadmeAssessment
from ghdtk.models.derived import DimensionId, DimensionScore
from ghdtk.models.raw import ProfileReadmeStatus
from ghdtk.scoring.framework import (
    ScoreInputs,
    metric_sources,
    metric_value,
)
from ghdtk.scoring.normalize import ScoredComponent, blend, normalize_ratio
from ghdtk.scoring.scorers.base import BaseScorer

_README_MIN_WORDS = 100


class ProfileScorer(BaseScorer):
    """Score the profile's presentation and README presence."""

    dimension = DimensionId.PRESENCE
    label = "Profile presence"

    def score(self, inputs: ScoreInputs) -> DimensionScore | None:
        presence = inputs.presence
        if presence is None:
            return None
        components = [self._fields_component(presence)]
        readme_clause = "no README assessed"
        if inputs.readme is not None:
            components.append(self._readme_component(inputs.readme))
            readme_clause = f"README status '{inputs.readme.status.value}'"
        score, breakdown = blend(components)
        total = len(presence.fields)
        present = sum(1 for field in presence.fields if field.status is FieldStatus.PRESENT)
        rationale = f"Profile field completeness {present}/{total} present; {readme_clause}"
        return self._result(score, rationale, breakdown)

    def _fields_component(self, presence: ProfilePresence) -> ScoredComponent:
        fields = presence.fields
        total = len(fields)
        present = sum(1 for field in fields if field.status is FieldStatus.PRESENT)
        value = normalize_ratio(present / total) if total else 0.0
        return ScoredComponent(
            component_id="profile_fields",
            label="Profile field completeness",
            value=value,
            weight=1.0,
            sources=tuple(ref for field in fields for ref in field.sources),
        )

    def _readme_component(self, readme: ReadmeAssessment) -> ScoredComponent:
        if readme.status is not ProfileReadmeStatus.PRESENT:
            evidence = tuple(readme.findings[0].evidence) if readme.findings else ()
            return ScoredComponent(
                component_id="profile_readme",
                label="Profile README quality",
                value=0.0,
                weight=1.0,
                sources=evidence,
            )

        words = int(metric_value(readme, "readme.word_count") or 0)
        headings = int(metric_value(readme, "readme.headings") or 0)
        code_blocks = int(metric_value(readme, "readme.code_blocks") or 0)
        links = int(metric_value(readme, "readme.links") or 0)
        images = int(metric_value(readme, "readme.images") or 0)
        badges = int(metric_value(readme, "readme.badges") or 0)
        mentions = int(metric_value(readme, "readme.username_mentions") or 0)
        boilerplate = bool(metric_value(readme, "readme.boilerplate") or False)

        word_component = normalize_ratio(min(words / _README_MIN_WORDS, 1.0))
        structure = (headings > 0, code_blocks > 0, links > 0, (images + badges) > 0)
        structure_component = normalize_ratio(sum(structure) / len(structure))
        personalization = 100.0 if mentions > 0 else 0.0
        if boilerplate:
            personalization = min(personalization, 50.0)

        value = 0.40 * word_component + 0.35 * structure_component + 0.25 * personalization
        sources = metric_sources(
            readme,
            "readme.word_count",
            "readme.headings",
            "readme.code_blocks",
            "readme.links",
            "readme.images",
            "readme.badges",
            "readme.username_mentions",
            "readme.boilerplate",
        )
        return ScoredComponent(
            component_id="profile_readme",
            label="Profile README quality",
            value=value,
            weight=1.0,
            sources=tuple(sources),
        )
