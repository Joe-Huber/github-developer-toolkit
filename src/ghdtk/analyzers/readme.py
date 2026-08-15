"""README quality & structure analysis (issue #26).

Assesses the profile README's structure and completeness with reproducible
signals: headings, word count, code blocks, links, images/badges, structured
sections (About / Skills / Contact) and personalization (username mentions and
generic boilerplate wording). Boilerplate detection is a documented heuristic
(:mod:`ghdtk.analyzers.heuristics`) with false-positive caveats; findings
reference the README and, where possible, the section or line that produced
them.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from ghdtk.analyzers.heuristics import find_boilerplate
from ghdtk.models.derived import (
    DimensionId,
    Finding,
    FindingSeverity,
    MetricRecord,
    SourceEntityKind,
    SourceReference,
)
from ghdtk.models.raw import ProfileReadme, ProfileReadmeStatus

_LOW_WORD_COUNT = 50

_SECTION_PATTERNS: dict[str, tuple[str, ...]] = {
    "about": ("about",),
    "skills": ("skill", "tech", "technolog", "stack", "tool"),
    "contact": ("contact", "reach me", "connect", "find me", "email me"),
}

_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})", re.MULTILINE)
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\([^)]*\)|<\s*https?://[^>]+>")
_BADGE_RE = re.compile(r"img\.shields\.io", re.IGNORECASE)
_WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)


class ReadmeAssessment(BaseModel):
    """The structured README quality assessment."""

    model_config = ConfigDict(frozen=True)

    username: str
    status: ProfileReadmeStatus
    metrics: list[MetricRecord]
    findings: list[Finding]


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _now(value: datetime | None) -> datetime:
    return value or datetime.now(UTC)


def _source(profile_readme: ProfileReadme, field: str) -> SourceReference:
    identifier = profile_readme.repository or profile_readme.username
    return SourceReference(entity=SourceEntityKind.README, identifier=identifier, field=field)


def _line_number(text: str, needle: str) -> int:
    lowered = needle.lower()
    for index, line in enumerate(text.splitlines(), start=1):
        if lowered in line.lower():
            return index
    return 0


def _heading_texts(text: str) -> list[str]:
    return [match.group(1).strip() for match in _HEADING_RE.finditer(text)]


def _count_fences(text: str) -> int:
    return len(_FENCE_RE.findall(text)) // 2


def _count_badges(text: str) -> int:
    return len(_BADGE_RE.findall(text))


def _count_username_mentions(text: str, username: str) -> int:
    plain = re.findall(rf"\b{re.escape(username)}\b", text, re.IGNORECASE)
    at = re.findall(rf"@\s*{re.escape(username)}\b", text, re.IGNORECASE)
    return len(plain) + len(at)


def _section_presence(headings: list[str]) -> dict[str, bool]:
    presence: dict[str, bool] = {name: False for name in _SECTION_PATTERNS}
    for heading in headings:
        lowered = heading.lower()
        for name, keywords in _SECTION_PATTERNS.items():
            if not presence[name] and any(keyword in lowered for keyword in keywords):
                presence[name] = True
    return presence


def assess_readme_quality(
    profile_readme: ProfileReadme,
    *,
    now: datetime | None = None,
) -> ReadmeAssessment:
    """Assess the structure and completeness of ``profile_readme``."""
    now = _now(now)
    username = profile_readme.username
    findings: list[Finding] = []
    metrics = [
        MetricRecord(
            id="readme.present",
            label="Profile README present",
            value=profile_readme.status == ProfileReadmeStatus.PRESENT,
            timestamp=now,
            sources=[_source(profile_readme, "content")],
        )
    ]

    if profile_readme.status != ProfileReadmeStatus.PRESENT:
        absent: dict[ProfileReadmeStatus, tuple[FindingSeverity, str, str]] = {
            ProfileReadmeStatus.NO_PROFILE_REPO: (
                FindingSeverity.LOW,
                "No profile repository",
                "There is no <username>/<username> repository, so no profile README can exist.",
            ),
            ProfileReadmeStatus.NO_README: (
                FindingSeverity.MEDIUM,
                "Profile repository has no README",
                "The profile repository exists but contains no README file.",
            ),
            ProfileReadmeStatus.EMPTY: (
                FindingSeverity.MEDIUM,
                "Profile README is empty",
                "The profile README exists but contains no content.",
            ),
            ProfileReadmeStatus.FETCH_FAILED: (
                FindingSeverity.LOW,
                "Profile README could not be fetched",
                f"Retrieval failed: {profile_readme.reason or 'unknown error'}.",
            ),
        }
        severity, title, message = absent[profile_readme.status]
        findings.append(
            Finding(
                id=f"readme.{profile_readme.status.value}",
                type="missing_information",
                severity=severity,
                title=title,
                message=message,
                dimension=DimensionId.DOCUMENTATION,
                evidence=[_source(profile_readme, "content")],
            )
        )
        return ReadmeAssessment(
            username=username,
            status=profile_readme.status,
            metrics=metrics,
            findings=findings,
        )

    content = profile_readme.content or ""
    source = _source(profile_readme, "content")

    word_count = len(_WORD_RE.findall(content))
    metrics.append(
        MetricRecord(
            id="readme.word_count",
            label="README word count",
            value=word_count,
            timestamp=now,
            sources=[source],
        )
    )
    if word_count < _LOW_WORD_COUNT:
        findings.append(
            Finding(
                id="readme.thin",
                type="quality_issue",
                severity=FindingSeverity.LOW,
                title="Profile README is very short",
                message=(
                    f"The README has only {word_count} words; "
                    f"consider adding more than the {_LOW_WORD_COUNT}-word minimum."
                ),
                dimension=DimensionId.DOCUMENTATION,
                evidence=[source],
            )
        )

    headings = _heading_texts(content)
    metrics.append(
        MetricRecord(
            id="readme.headings",
            label="README headings",
            value=len(headings),
            timestamp=now,
            sources=[source],
        )
    )
    top_level = next((heading for heading in headings if heading.lower() != "readme"), None)
    if top_level is None:
        findings.append(
            Finding(
                id="readme.no_heading",
                type="quality_issue",
                severity=FindingSeverity.LOW,
                title="README has no content heading",
                message="The README has no heading besides a bare 'README' title.",
                dimension=DimensionId.DOCUMENTATION,
                evidence=[source],
            )
        )

    code_blocks = _count_fences(content)
    metrics.append(
        MetricRecord(
            id="readme.code_blocks",
            label="README code blocks",
            value=code_blocks,
            timestamp=now,
            sources=[source],
        )
    )

    links = len(_LINK_RE.findall(content))
    metrics.append(
        MetricRecord(
            id="readme.links",
            label="README links",
            value=links,
            timestamp=now,
            sources=[source],
        )
    )

    images = len(_IMAGE_RE.findall(content))
    metrics.append(
        MetricRecord(
            id="readme.images",
            label="README images",
            value=images,
            timestamp=now,
            sources=[source],
        )
    )

    badges = _count_badges(content)
    metrics.append(
        MetricRecord(
            id="readme.badges",
            label="README badges",
            value=badges,
            timestamp=now,
            sources=[source],
        )
    )

    sections = _section_presence(headings)
    section_labels = {"about": "About", "skills": "Skills", "contact": "Contact"}
    for name, present in sections.items():
        field = f"content:section:{name}"
        metrics.append(
            MetricRecord(
                id=f"readme.section.{name}",
                label=f"{section_labels[name]} section",
                value=present,
                timestamp=now,
                sources=[_source(profile_readme, field)],
            )
        )
        if not present:
            findings.append(
                Finding(
                    id=f"readme.section.{name}.missing",
                    type="missing_information",
                    severity=FindingSeverity.LOW,
                    title=f"No {section_labels[name]} section",
                    message=(
                        f"The README has no {section_labels[name].lower()}-oriented heading "
                        f"(keywords: {', '.join(_SECTION_PATTERNS[name])})."
                    ),
                    dimension=DimensionId.DOCUMENTATION,
                    evidence=[_source(profile_readme, field)],
                )
            )

    mentions = _count_username_mentions(content, username)
    metrics.append(
        MetricRecord(
            id="readme.username_mentions",
            label="Username mentions",
            value=mentions,
            timestamp=now,
            sources=[source],
        )
    )
    if mentions == 0:
        findings.append(
            Finding(
                id="readme.not_personalized",
                type="quality_issue",
                severity=FindingSeverity.LOW,
                title="Profile README does not mention the account",
                message=(
                    f"The README never mentions {username}; a personal touch makes "
                    "a profile README recognizable."
                ),
                dimension=DimensionId.DOCUMENTATION,
                evidence=[source],
            )
        )

    boilerplate = find_boilerplate(content)
    if boilerplate:
        phrase = boilerplate[0]
        line = _line_number(content, phrase)
        field = f"content:line:{line}" if line else "content"
        findings.append(
            Finding(
                id="readme.boilerplate",
                type="quality_issue",
                severity=FindingSeverity.MEDIUM,
                title="Generic template wording detected",
                message=(
                    f"The README contains template wording such as "
                    f"'{phrase}'; verify it is genuinely personalized. "
                    "Heuristic match, may be a false positive."
                ),
                dimension=DimensionId.DOCUMENTATION,
                evidence=[_source(profile_readme, field)],
            )
        )

    return ReadmeAssessment(
        username=username,
        status=profile_readme.status,
        metrics=metrics,
        findings=findings,
    )


__all__ = ["ReadmeAssessment", "assess_readme_quality"]
