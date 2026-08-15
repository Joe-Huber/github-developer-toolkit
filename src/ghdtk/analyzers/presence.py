"""Profile metadata & presentation analysis (issue #24).

Assesses the presence and quality of a profile's presentation fields — bio,
website, social links, location, company, hireable flag and account age.
Placeholder/stale-value detection is a documented heuristic
(:mod:`ghdtk.analyzers.heuristics`); findings carry per-field evidence so a
"no bio" or "placeholder bio detected" conclusion always points at the raw
field that produced it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ghdtk.analyzers.heuristics import find_placeholders
from ghdtk.models.derived import (
    DimensionId,
    Finding,
    FindingSeverity,
    MetricRecord,
    SourceEntityKind,
    SourceReference,
)
from ghdtk.models.raw import User

_RECENT_ACCOUNT_DAYS = 90
_SHORT_BIO_WORDS = 5


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class FieldStatus(StrEnum):
    """Assessment of one profile field."""

    PRESENT = "present"
    MISSING = "missing"
    PLACEHOLDER = "placeholder"


class FieldAssessment(BaseModel):
    """Per-field presence/quality verdict with provenance."""

    model_config = ConfigDict(frozen=True)

    field: str
    label: str
    status: FieldStatus
    value: str | None = None
    reason: str | None = None
    sources: list[SourceReference] = Field(default_factory=list)


class ProfilePresence(BaseModel):
    """The structured profile-presentation assessment."""

    model_config = ConfigDict(frozen=True)

    username: str
    fields: list[FieldAssessment]
    metrics: list[MetricRecord]
    findings: list[Finding]


_TEXT_FIELDS: tuple[tuple[str, str], ...] = (
    ("name", "Display name"),
    ("bio", "Bio"),
    ("blog", "Website"),
    ("company", "Company"),
    ("location", "Location"),
    ("email", "Email"),
    ("twitter_username", "Twitter handle"),
)

_MISSING_SEVERITY: dict[str, FindingSeverity] = {
    "name": FindingSeverity.LOW,
    "bio": FindingSeverity.MEDIUM,
    "blog": FindingSeverity.MEDIUM,
    "company": FindingSeverity.LOW,
    "location": FindingSeverity.LOW,
    "email": FindingSeverity.LOW,
    "twitter_username": FindingSeverity.LOW,
}

_MISSING_MESSAGE: dict[str, str] = {
    "name": "No display name is set; profiles without a name are harder to recognize.",
    "bio": "No bio is set; the bio is the first line of a profile's story.",
    "blog": "No website is set; a personal site or portfolio is a strong signal.",
    "company": "No company is listed; optional but useful context for recruiters.",
    "location": "No location is set; optional but adds useful context.",
    "email": "No public email is set; note that GitHub hides email unless it is made public.",
    "twitter_username": "No Twitter handle is set; an easy way to cross-link social presence.",
}

_PLACEHOLDER_SEVERITY: dict[str, FindingSeverity] = {
    "bio": FindingSeverity.HIGH,
    "blog": FindingSeverity.HIGH,
    "company": FindingSeverity.MEDIUM,
    "name": FindingSeverity.MEDIUM,
    "location": FindingSeverity.MEDIUM,
    "email": FindingSeverity.MEDIUM,
    "twitter_username": FindingSeverity.MEDIUM,
}

_PLACEHOLDER_MESSAGE: dict[str, str] = {
    "bio": "The bio still carries placeholder text; replace it with a real description.",
    "blog": "The website still carries a placeholder; point it at a real site.",
    "company": "The company field still carries placeholder text.",
    "name": "The display name looks like a placeholder.",
    "location": "The location field looks like a placeholder.",
    "email": "The email field looks like a placeholder.",
    "twitter_username": "The Twitter handle looks like a placeholder.",
}


def _now(value: datetime | None) -> datetime:
    return value or datetime.now(UTC)


def _source(user: User, field: str) -> SourceReference:
    return SourceReference(entity=SourceEntityKind.USER, identifier=user.login, field=field)


def assess_profile_presence(
    user: User,
    *,
    now: datetime | None = None,
) -> ProfilePresence:
    """Assess the presentation quality of ``user``'s profile fields."""
    now = _now(now)
    fields: list[FieldAssessment] = []
    findings: list[Finding] = []
    placeholder_counts: dict[str, list[str]] = {}

    for field, label in _TEXT_FIELDS:
        raw = getattr(user, field)
        value = (raw or "").strip()
        source = _source(user, field)
        if not value:
            fields.append(
                FieldAssessment(
                    field=field,
                    label=label,
                    status=FieldStatus.MISSING,
                    sources=[source],
                )
            )
            findings.append(
                Finding(
                    id=f"presence.{field}.missing",
                    type="missing_information",
                    severity=_MISSING_SEVERITY[field],
                    title=f"No {label.lower()} set",
                    message=_MISSING_MESSAGE[field],
                    dimension=DimensionId.PRESENCE,
                    evidence=[source],
                )
            )
            continue
        matches = find_placeholders(value)
        if matches:
            fields.append(
                FieldAssessment(
                    field=field,
                    label=label,
                    status=FieldStatus.PLACEHOLDER,
                    value=value,
                    reason="placeholder text detected",
                    sources=[source],
                )
            )
            placeholder_counts[field] = matches
            findings.append(
                Finding(
                    id=f"presence.{field}.placeholder",
                    type="placeholder_value",
                    severity=_PLACEHOLDER_SEVERITY[field],
                    title=f"Placeholder {label.lower()} detected",
                    message=_PLACEHOLDER_MESSAGE[field],
                    dimension=DimensionId.PRESENCE,
                    evidence=[source],
                )
            )
            continue
        fields.append(
            FieldAssessment(
                field=field,
                label=label,
                status=FieldStatus.PRESENT,
                value=value,
                sources=[source],
            )
        )

    if user.bio and len(user.bio.split()) < _SHORT_BIO_WORDS:
        findings.append(
            Finding(
                id="presence.bio.short",
                type="quality_issue",
                severity=FindingSeverity.LOW,
                title="Bio is very short",
                message=f"The bio has fewer than {_SHORT_BIO_WORDS} words; it may not convey much.",
                dimension=DimensionId.PRESENCE,
                evidence=[_source(user, "bio")],
            )
        )

    hireable_source = _source(user, "hireable")
    if user.hireable is None:
        fields.append(
            FieldAssessment(
                field="hireable",
                label="Hireable flag",
                status=FieldStatus.MISSING,
                reason="not set",
                sources=[hireable_source],
            )
        )
        findings.append(
            Finding(
                id="presence.hireable.unset",
                type="missing_information",
                severity=FindingSeverity.LOW,
                title="Hireable flag not set",
                message="The hireable flag is not set; set it to signal availability.",
                dimension=DimensionId.PRESENCE,
                evidence=[hireable_source],
            )
        )
    else:
        fields.append(
            FieldAssessment(
                field="hireable",
                label="Hireable flag",
                status=FieldStatus.PRESENT,
                value=str(user.hireable).lower(),
                sources=[hireable_source],
            )
        )

    if user.created_at is not None:
        account_age_days = max(
            0, int((now - _ensure_utc(user.created_at)).total_seconds() // 86400)
        )
        fields.append(
            FieldAssessment(
                field="account_age",
                label="Account age",
                status=FieldStatus.PRESENT,
                value=f"{account_age_days} days",
                sources=[_source(user, "created_at")],
            )
        )
        if account_age_days < _RECENT_ACCOUNT_DAYS:
            findings.append(
                Finding(
                    id="presence.account.recent",
                    type="quality_issue",
                    severity=FindingSeverity.LOW,
                    title="Recently created account",
                    message=(
                        f"The account is only {account_age_days} days old; "
                        "activity history is still building up."
                    ),
                    dimension=DimensionId.PRESENCE,
                    evidence=[_source(user, "created_at")],
                )
            )
    else:
        fields.append(
            FieldAssessment(
                field="account_age",
                label="Account age",
                status=FieldStatus.MISSING,
                reason="created_at not available",
                sources=[_source(user, "created_at")],
            )
        )

    by_status: dict[FieldStatus, int] = {}
    for assessment in fields:
        by_status[assessment.status] = by_status.get(assessment.status, 0) + 1
    total = len(fields)
    present = by_status.get(FieldStatus.PRESENT, 0)
    missing = by_status.get(FieldStatus.MISSING, 0)
    placeholders = by_status.get(FieldStatus.PLACEHOLDER, 0)
    all_sources = [assessment.sources[0] for assessment in fields if assessment.sources]

    metrics = [
        MetricRecord(
            id="presence.fields.total",
            label="Profile fields assessed",
            value=total,
            timestamp=now,
            sources=all_sources,
        ),
        MetricRecord(
            id="presence.fields.present",
            label="Profile fields populated",
            value=present,
            timestamp=now,
            sources=all_sources,
        ),
        MetricRecord(
            id="presence.fields.missing",
            label="Profile fields missing",
            value=missing,
            timestamp=now,
            sources=all_sources,
        ),
        MetricRecord(
            id="presence.fields.placeholder",
            label="Profile fields with placeholder text",
            value=placeholders,
            timestamp=now,
            sources=[
                _source(user, field) for field, _ in _TEXT_FIELDS if field in placeholder_counts
            ],
            confidence=0.9,
        ),
        MetricRecord(
            id="presence.completeness",
            label="Profile completeness",
            value=present / total if total else 0.0,
            timestamp=now,
            sources=all_sources,
        ),
    ]
    if user.created_at is not None:
        metrics.append(
            MetricRecord(
                id="presence.account_age_days",
                label="Account age (days)",
                value=account_age_days,
                timestamp=now,
                sources=[_source(user, "created_at")],
            )
        )

    return ProfilePresence(username=user.login, fields=fields, metrics=metrics, findings=findings)


__all__ = [
    "FieldAssessment",
    "FieldStatus",
    "ProfilePresence",
    "assess_profile_presence",
]
