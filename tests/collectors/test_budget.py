"""Unit tests for the request budget planner (issue #22)."""

from __future__ import annotations

import pytest

from ghdtk.collectors.budget import CollectionBudget


def test_rejects_non_positive_cap() -> None:
    with pytest.raises(ValueError):
        CollectionBudget(0)
    with pytest.raises(ValueError):
        CollectionBudget(-5)


def test_initial_state() -> None:
    budget = CollectionBudget(5)
    assert budget.max_requests == 5
    assert budget.used == 0
    assert budget.remaining == 5
    assert budget.can_run(5) is True
    assert budget.can_run(6) is False


def test_consume_and_can_run() -> None:
    budget = CollectionBudget(5)
    budget.consume(2)
    assert budget.used == 2
    assert budget.remaining == 3
    assert budget.can_run(3) is True
    assert budget.can_run(4) is False


def test_consume_ignores_negative_amounts() -> None:
    budget = CollectionBudget(3)
    budget.consume(-3)
    assert budget.used == 0
    assert budget.remaining == 3


def test_remaining_never_negative() -> None:
    budget = CollectionBudget(3)
    budget.consume(10)
    assert budget.used == 10
    assert budget.remaining == 0
    assert budget.can_run(1) is False
