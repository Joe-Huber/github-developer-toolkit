"""Tests for the open-source dimension scorer (issue #49)."""

from __future__ import annotations

import pytest

from ghdtk.analyzers.pull_requests import PullRequestAnalysis
from ghdtk.models.derived import DimensionId
from ghdtk.scoring import ScoreInputs
from ghdtk.scoring.scorers.open_source import OpenSourceScorer


def _prs(
    *,
    total: int,
    merge_rate: float | None = None,
    external_share: float | None = None,
    reviewed_share: float | None = None,
) -> PullRequestAnalysis:
    return PullRequestAnalysis(
        username="octocat",
        total_pull_requests=total,
        open_count=0,
        merged_count=0,
        closed_count=0,
        closed_unmerged_count=0,
        merge_rate=merge_rate,
        external_share=external_share,
        reviewed_share=reviewed_share,
        per_repo_counts={},
        metrics=[],
        findings=[],
    )


def test_high_volume_accepted_and_external_scores_high() -> None:
    result = OpenSourceScorer().score(
        ScoreInputs(
            pull_requests=_prs(
                total=400,
                merge_rate=0.9,
                external_share=0.8,
                reviewed_share=0.6,
            )
        )
    )
    assert result is not None
    assert result.dimension is DimensionId.OPEN_SOURCE
    assert result.score == 85.0
    assert sum(item.contribution for item in result.breakdown) == pytest.approx(85.0)


def test_no_pull_requests_scores_zero() -> None:
    result = OpenSourceScorer().score(ScoreInputs(pull_requests=_prs(total=0)))
    assert result is not None
    assert result.score == 0.0


def test_mid_range_pull_requests() -> None:
    result = OpenSourceScorer().score(
        ScoreInputs(
            pull_requests=_prs(
                total=150,
                merge_rate=0.5,
                external_share=0.5,
                reviewed_share=0.3,
            )
        )
    )
    assert result is not None
    assert result.score == pytest.approx(57.35, abs=0.005)


def test_without_pull_request_analysis_dimension_is_unscorable() -> None:
    assert OpenSourceScorer().score(ScoreInputs()) is None
