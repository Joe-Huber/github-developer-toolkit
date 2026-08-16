"""Tests for the profile dimension scorer (issue #48)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ghdtk.analyzers.presence import FieldAssessment, FieldStatus, ProfilePresence
from ghdtk.analyzers.readme import ReadmeAssessment
from ghdtk.models.derived import DimensionId, Finding, MetricRecord
from ghdtk.models.raw import ProfileReadmeStatus
from ghdtk.scoring import ScoreInputs
from ghdtk.scoring.scorers.profile import ProfileScorer

NOW = datetime(2026, 1, 1, tzinfo=UTC)

_FIELDS = ("bio", "website", "location", "company")


def _field(name: str, status: FieldStatus) -> FieldAssessment:
    return FieldAssessment(field=name, label=name, status=status)


def _presence(statuses: list[FieldStatus]) -> ProfilePresence:
    fields = [_field(name, status) for name, status in zip(_FIELDS, statuses, strict=True)]
    return ProfilePresence(username="octocat", fields=fields, metrics=[], findings=[])


def _metric(metric_id: str, value: object) -> MetricRecord:
    return MetricRecord(
        id=metric_id,
        label=metric_id,
        value=value,
        sources=[],
        timestamp=NOW,
    )


def _readme(
    status: ProfileReadmeStatus = ProfileReadmeStatus.PRESENT,
    *,
    metrics: list[MetricRecord] | None = None,
    findings: list[Finding] | None = None,
) -> ReadmeAssessment:
    return ReadmeAssessment(
        username="octocat",
        status=status,
        metrics=metrics or [],
        findings=findings or [],
    )


def _rich_readme_metrics() -> list[MetricRecord]:
    return [
        _metric("readme.word_count", 250),
        _metric("readme.headings", 5),
        _metric("readme.code_blocks", 2),
        _metric("readme.links", 4),
        _metric("readme.images", 1),
        _metric("readme.badges", 2),
        _metric("readme.username_mentions", 3),
        _metric("readme.boilerplate", False),
    ]


def _score(
    statuses: list[FieldStatus],
    readme: ReadmeAssessment | None = None,
) -> float:
    result = ProfileScorer().score(ScoreInputs(presence=_presence(statuses), readme=readme))
    assert result is not None
    return result.score


def test_full_presence_and_rich_readme_scores_100() -> None:
    result = ProfileScorer().score(
        ScoreInputs(
            presence=_presence([FieldStatus.PRESENT] * 4),
            readme=_readme(metrics=_rich_readme_metrics()),
        )
    )
    assert result is not None
    assert result.dimension is DimensionId.PRESENCE
    assert result.score == 100.0
    assert result.rationale == "Profile field completeness 4/4 present; README status 'present'"
    assert [item.component_id for item in result.breakdown] == [
        "profile_fields",
        "profile_readme",
    ]
    assert all(item.weight == pytest.approx(0.5) for item in result.breakdown)
    assert sum(item.contribution for item in result.breakdown) == pytest.approx(100.0)


def test_sparse_fields_and_missing_readme_score_low() -> None:
    assert (
        _score(
            [FieldStatus.PRESENT] + [FieldStatus.MISSING] * 3,
            _readme(status=ProfileReadmeStatus.NO_README),
        )
        == 12.5
    )


def test_presence_only_renormalizes_without_readme() -> None:
    result = ProfileScorer().score(
        ScoreInputs(presence=_presence([FieldStatus.PRESENT] * 3 + [FieldStatus.MISSING]))
    )
    assert result is not None
    assert result.score == 75.0
    assert len(result.breakdown) == 1
    assert result.breakdown[0].weight == 1.0


def test_thin_unstructured_readme_drags_presence() -> None:
    thin = [
        _metric("readme.word_count", 30),
        _metric("readme.headings", 0),
        _metric("readme.code_blocks", 0),
        _metric("readme.links", 0),
        _metric("readme.images", 0),
        _metric("readme.badges", 0),
        _metric("readme.username_mentions", 0),
        _metric("readme.boilerplate", False),
    ]
    assert _score([FieldStatus.PRESENT] * 4, _readme(metrics=thin)) == 56.0


def test_boilerplate_readme_caps_personalization() -> None:
    boilerplate = _rich_readme_metrics()
    boilerplate[-1] = _metric("readme.boilerplate", True)
    assert _score([FieldStatus.PRESENT] * 4, _readme(metrics=boilerplate)) == pytest.approx(93.75)


def test_empty_readme_scores_zero_on_readme_component() -> None:
    assert (
        _score(
            [FieldStatus.PRESENT] * 4,
            _readme(status=ProfileReadmeStatus.EMPTY),
        )
        == 50.0
    )


def test_without_presence_analysis_dimension_is_unscorable() -> None:
    assert ProfileScorer().score(ScoreInputs()) is None
