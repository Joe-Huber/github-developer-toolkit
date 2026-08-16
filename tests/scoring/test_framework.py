"""Tests for the scoring framework (issue #47)."""

from __future__ import annotations

from datetime import UTC, datetime

from ghdtk.analyzers.presence import ProfilePresence
from ghdtk.models.derived import (
    DimensionId,
    DimensionScore,
    MetricRecord,
    SourceEntityKind,
    SourceReference,
)
from ghdtk.scoring import (
    ScoreInputs,
    ScoringConfig,
    ScoringRegistry,
    dedupe_sources,
    default_weights,
    dimension_label,
    metric_sources,
    metric_value,
)
from ghdtk.scoring.scorers.base import BaseScorer

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _metric(metric_id: str, value: object) -> MetricRecord:
    return MetricRecord(
        id=metric_id,
        label=metric_id,
        value=value,
        sources=[],
        timestamp=NOW,
    )


class _FakeResult:
    def __init__(self, metrics: list[MetricRecord]) -> None:
        self.metrics = metrics


class _FakeScorer(BaseScorer):
    dimension = DimensionId.PRESENCE
    label = "Profile presence"

    def __init__(self, config: ScoringConfig | None = None) -> None:
        super().__init__(config)
        self.calls = 0

    def score(self, inputs: ScoreInputs) -> DimensionScore | None:
        self.calls += 1
        if inputs.presence is None:
            return None
        return self._result(42.0, "fake", [])


def test_score_inputs_defaults_to_unavailable() -> None:
    inputs = ScoreInputs()
    for name in (
        "presence",
        "readme",
        "repository_quality",
        "repository_activity",
        "portfolio",
        "stars",
        "network",
        "commits",
        "contribution_calendar",
        "pull_requests",
        "languages",
    ):
        assert getattr(inputs, name) is None


def test_scoring_config_default_weights_cover_all_dimensions() -> None:
    config = ScoringConfig()
    assert set(config.weights) == set(DimensionId) - {DimensionId.DOCUMENTATION}
    assert all(weight > 0 for weight in config.weights.values())
    assert default_weights() == config.weights


def test_scoring_config_from_settings_reads_scoring_fields() -> None:
    settings = type(
        "Settings",
        (),
        {
            "scoring_strength_threshold": 80.0,
            "scoring_gap_bad_days": 45,
            "unrelated_field": 999,
        },
    )
    config = ScoringConfig.from_settings(settings)
    assert config.strength_threshold == 80.0
    assert config.gap_bad_days == 45
    assert config.cadence_target == 4.0


def test_scoring_config_from_settings_ignores_missing_fields() -> None:
    config = ScoringConfig.from_settings(object())
    assert config == ScoringConfig()


def test_registry_reports_dimensions_in_order() -> None:
    registry = ScoringRegistry([_FakeScorer()])
    assert registry.dimensions() == [DimensionId.PRESENCE]


def _presence() -> ProfilePresence:
    return ProfilePresence(username="octocat", fields=[], metrics=[], findings=[])


def test_registry_score_all_skips_unscorable_dimensions() -> None:
    scorer = _FakeScorer()
    registry = ScoringRegistry([scorer])
    assert registry.score_all(ScoreInputs()) == []
    assert scorer.calls == 1
    scored = registry.score_all(ScoreInputs(presence=_presence()))
    assert len(scored) == 1
    assert scored[0].score == 42.0


def test_registry_applies_configured_weights() -> None:
    config = ScoringConfig(weights={DimensionId.PRESENCE: 2.5})
    registry = ScoringRegistry([_FakeScorer(config)], config=config)
    scored = registry.score_all(ScoreInputs(presence=_presence()))
    assert scored[0].weight == 2.5


def test_metric_value_finds_or_returns_none() -> None:
    result = _FakeResult([_metric("a.value", 3)])
    assert metric_value(result, "a.value") == 3
    assert metric_value(result, "missing") is None


def test_metric_sources_deduplicates_across_metrics() -> None:
    shared = SourceReference(
        entity=SourceEntityKind.PROFILE,
        identifier="octocat",
        field="bio",
    )
    result = _FakeResult(
        [
            _metric_with_source("a.value", shared),
            _metric_with_source("b.value", shared),
        ]
    )
    sources = metric_sources(result, "a.value", "b.value")
    assert len(sources) == 1
    assert sources[0] == shared


def test_dedupe_sources_preserves_first_seen_order() -> None:
    first = SourceReference(entity=SourceEntityKind.PROFILE, identifier="octocat", field="bio")
    second = SourceReference(
        entity=SourceEntityKind.REPOSITORY, identifier="octocat/repo", field="name"
    )
    assert dedupe_sources([first, second, first]) == [first, second]


def test_dimension_label_falls_back_to_value() -> None:
    assert dimension_label(DimensionId.ACTIVITY) == "Activity"
    assert dimension_label(DimensionId.CONSISTENCY) == "Consistency"


def _metric_with_source(metric_id: str, source: SourceReference) -> MetricRecord:
    return MetricRecord(
        id=metric_id,
        label=metric_id,
        value=1,
        sources=[source],
        timestamp=NOW,
    )
