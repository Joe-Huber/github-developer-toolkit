"""Unit tests for profile metadata & presentation analysis (issue #24).

Exercises the analyzer against complete, minimal and placeholder-heavy
fixture profiles, verifying per-field assessments, placeholder/stale-value
heuristics, and evidence provenance.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ghdtk.analyzers import assess_profile_presence
from ghdtk.models.derived import DimensionId, FindingSeverity, SourceEntityKind
from ghdtk.models.raw import User

FixtureLoader = Any

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _user(load_raw_fixture: FixtureLoader, name: str) -> User:
    return User.model_validate(load_raw_fixture(name))


def test_complete_profile(load_raw_fixture: FixtureLoader) -> None:
    result = assess_profile_presence(_user(load_raw_fixture, "user"), now=NOW)

    assert result.username == "octocat"
    by_field = {field.field: field for field in result.fields}
    assert by_field["name"].status.value == "present"
    assert by_field["bio"].status.value == "present"
    assert by_field["blog"].status.value == "present"
    assert by_field["company"].status.value == "present"
    assert by_field["location"].status.value == "present"
    assert by_field["email"].status.value == "present"
    assert by_field["twitter_username"].status.value == "present"
    assert by_field["hireable"].status.value == "present"
    assert by_field["account_age"].status.value == "present"

    metric_by_id = {metric.id: metric for metric in result.metrics}
    assert metric_by_id["presence.fields.present"].value == 9
    assert metric_by_id["presence.fields.total"].value == 9
    assert metric_by_id["presence.completeness"].value == 1.0
    assert metric_by_id["presence.account_age_days"].value == 6561

    finding_ids = {finding.id for finding in result.findings}
    assert "presence.bio.missing" not in finding_ids
    assert "presence.blog.missing" not in finding_ids
    assert "presence.hireable.unset" not in finding_ids


def test_complete_profile_short_bio_is_flagged(load_raw_fixture: FixtureLoader) -> None:
    result = assess_profile_presence(_user(load_raw_fixture, "user"), now=NOW)

    short_bio = next(finding for finding in result.findings if finding.id == "presence.bio.short")
    assert short_bio.severity is FindingSeverity.LOW
    assert short_bio.dimension is DimensionId.PRESENCE
    assert short_bio.evidence[0].field == "bio"
    assert short_bio.evidence[0].entity is SourceEntityKind.USER


def test_minimal_profile(load_raw_fixture: FixtureLoader) -> None:
    result = assess_profile_presence(_user(load_raw_fixture, "user_minimal"), now=NOW)

    by_status: dict[str, int] = {}
    for field in result.fields:
        by_status[field.status.value] = by_status.get(field.status.value, 0) + 1
    assert by_status == {"missing": 8, "present": 1}

    finding_ids = {finding.id for finding in result.findings}
    assert {
        "presence.name.missing",
        "presence.bio.missing",
        "presence.blog.missing",
        "presence.company.missing",
        "presence.location.missing",
        "presence.email.missing",
        "presence.twitter_username.missing",
        "presence.hireable.unset",
    } <= finding_ids

    bio = next(finding for finding in result.findings if finding.id == "presence.bio.missing")
    assert bio.severity is FindingSeverity.MEDIUM
    website = next(finding for finding in result.findings if finding.id == "presence.blog.missing")
    assert website.severity is FindingSeverity.MEDIUM
    hireable = next(
        finding for finding in result.findings if finding.id == "presence.hireable.unset"
    )
    assert hireable.severity is FindingSeverity.LOW
    assert hireable.evidence[0].field == "hireable"

    metric_by_id = {metric.id: metric for metric in result.metrics}
    assert metric_by_id["presence.completeness"].value == 1 / 9


def test_minimal_profile_recent_account(load_raw_fixture: FixtureLoader) -> None:
    user = _user(load_raw_fixture, "user_minimal").model_copy(
        update={"created_at": datetime(2025, 12, 1, tzinfo=UTC)}
    )
    result = assess_profile_presence(user, now=NOW)

    recent = next(finding for finding in result.findings if finding.id == "presence.account.recent")
    assert recent.severity is FindingSeverity.LOW
    assert recent.evidence[0].field == "created_at"
    assert recent.evidence[0].identifier == "minimaldev"


def test_placeholder_heavy_profile(load_raw_fixture: FixtureLoader) -> None:
    result = assess_profile_presence(_user(load_raw_fixture, "user_placeholder"), now=NOW)

    by_field = {field.field: field for field in result.fields}
    assert by_field["name"].status.value == "placeholder"
    assert by_field["bio"].status.value == "placeholder"
    assert by_field["blog"].status.value == "placeholder"
    assert by_field["company"].status.value == "placeholder"
    assert by_field["location"].status.value == "present"
    assert by_field["email"].status.value == "missing"
    assert by_field["twitter_username"].status.value == "missing"
    assert by_field["hireable"].status.value == "present"

    placeholder_findings = {
        finding.id: finding for finding in result.findings if finding.type == "placeholder_value"
    }
    assert {
        "presence.name.placeholder",
        "presence.bio.placeholder",
        "presence.blog.placeholder",
        "presence.company.placeholder",
    } == set(placeholder_findings)
    assert placeholder_findings["presence.bio.placeholder"].severity is FindingSeverity.HIGH
    assert placeholder_findings["presence.blog.placeholder"].severity is FindingSeverity.HIGH
    assert placeholder_findings["presence.company.placeholder"].severity is FindingSeverity.MEDIUM

    metric_by_id = {metric.id: metric for metric in result.metrics}
    assert metric_by_id["presence.fields.placeholder"].value == 4
    assert metric_by_id["presence.fields.placeholder"].confidence < 1.0
    assert metric_by_id["presence.completeness"].value == 3 / 9


def test_findings_reference_source_fields(load_raw_fixture: FixtureLoader) -> None:
    result = assess_profile_presence(_user(load_raw_fixture, "user_placeholder"), now=NOW)

    for finding in result.findings:
        assert finding.evidence, f"{finding.id} has no evidence"
        for source in finding.evidence:
            assert source.entity is SourceEntityKind.USER
            assert source.identifier == "placeholderuser"
            assert source.field is not None


def test_hireable_true_is_present(load_raw_fixture: FixtureLoader) -> None:
    user = _user(load_raw_fixture, "user_minimal").model_copy(update={"hireable": True})
    result = assess_profile_presence(user, now=NOW)

    hireable = next(field for field in result.fields if field.field == "hireable")
    assert hireable.status.value == "present"
    assert hireable.value == "true"
    assert not any(finding.id == "presence.hireable.unset" for finding in result.findings)
