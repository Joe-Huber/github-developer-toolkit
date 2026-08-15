"""Tests for the scoring normalization helpers (issue #47)."""

from __future__ import annotations

import pytest

from ghdtk.scoring import (
    ScoredComponent,
    blend,
    clamp,
    normalize_linear,
    normalize_log,
    normalize_ratio,
)


def test_clamp_bounds_and_midpoint() -> None:
    assert clamp(-5.0) == 0.0
    assert clamp(150.0) == 100.0
    assert clamp(42.0) == 42.0
    assert clamp(42.0, low=10.0, high=50.0) == 42.0


def test_normalize_ratio_clamps_out_of_range() -> None:
    assert normalize_ratio(0.5) == 50.0
    assert normalize_ratio(-0.2) == 0.0
    assert normalize_ratio(1.4) == 100.0
    assert normalize_ratio(0.3, scale=10.0) == 3.0


def test_normalize_linear_maps_and_clamps() -> None:
    assert normalize_linear(50.0, 0.0, 100.0) == 50.0
    assert normalize_linear(-10.0, 0.0, 100.0) == 0.0
    assert normalize_linear(150.0, 0.0, 100.0) == 100.0


def test_normalize_linear_inverted() -> None:
    assert normalize_linear(0.0, 0.0, 100.0, high_is_good=False) == 100.0
    assert normalize_linear(50.0, 0.0, 100.0, high_is_good=False) == 50.0
    assert normalize_linear(100.0, 0.0, 100.0, high_is_good=False) == 0.0


def test_normalize_linear_degenerate_range() -> None:
    assert normalize_linear(50.0, 10.0, 10.0) == 100.0
    assert normalize_linear(5.0, 10.0, 10.0) == 0.0
    assert normalize_linear(5.0, 10.0, 10.0, high_is_good=False) == 100.0


def test_normalize_linear_high_is_good_gap_between_anchors() -> None:
    assert normalize_linear(7.0, 14.0, 60.0, high_is_good=False) == 100.0
    assert normalize_linear(60.0, 14.0, 60.0, high_is_good=False) == 0.0
    assert normalize_linear(37.0, 14.0, 60.0, high_is_good=False) == pytest.approx(50.0)


def test_normalize_log_scales() -> None:
    assert normalize_log(0.0, 1.0, 1000.0) == 0.0
    assert normalize_log(1.0, 1.0, 1000.0) == 0.0
    assert normalize_log(100.0, 1.0, 1000.0) == pytest.approx(2 / 3 * 100)
    assert normalize_log(2000.0, 1.0, 1000.0) == 100.0


def test_normalize_log_rejects_invalid_range() -> None:
    with pytest.raises(ValueError):
        normalize_log(10.0, 0.0, 1000.0)
    with pytest.raises(ValueError):
        normalize_log(10.0, 100.0, 10.0)


def test_blend_averages_components_and_builds_breakdown() -> None:
    components = [
        ScoredComponent(component_id="a", label="A", value=100.0, weight=1.0),
        ScoredComponent(component_id="b", label="B", value=50.0, weight=1.0),
    ]
    score, breakdown = blend(components)
    assert score == 75.0
    assert [item.component_id for item in breakdown] == ["a", "b"]
    assert sum(item.contribution for item in breakdown) == pytest.approx(score)
    assert sum(item.weight for item in breakdown) == pytest.approx(1.0)
    assert breakdown[0].contribution == 50.0


def test_blend_respects_relative_weights() -> None:
    components = [
        ScoredComponent(component_id="a", label="A", value=100.0, weight=3.0),
        ScoredComponent(component_id="b", label="B", value=0.0, weight=1.0),
    ]
    score, breakdown = blend(components)
    assert score == 75.0
    assert breakdown[0].weight == pytest.approx(0.75)
    assert breakdown[0].contribution == pytest.approx(75.0)


def test_blend_empty_and_zero_weight() -> None:
    assert blend([]) == (0.0, [])
    components = [ScoredComponent(component_id="a", label="A", value=100.0, weight=0.0)]
    score, breakdown = blend(components)
    assert score == 0.0
    assert breakdown == []
