"""Unit tests for the request budget planner (issues #22, #63).

Issue #63 adds reservation-based accounting so the orchestrator can run
parallel collections without letting their combined bursts exceed the cap.
"""

from __future__ import annotations

import threading

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


# --- reservation accounting (issue #63) -----------------------------------


def test_reserve_commits_estimated_cost() -> None:
    budget = CollectionBudget(5)
    assert budget.reserve(3) is True
    assert budget.used == 3
    assert budget.remaining == 2


def test_reserve_fails_when_burst_does_not_fit() -> None:
    budget = CollectionBudget(5)
    assert budget.reserve(5) is True
    assert budget.reserve(1) is False
    assert budget.used == 5
    assert budget.can_run(1) is False


def test_reserve_does_not_mutate_on_failure() -> None:
    budget = CollectionBudget(3)
    assert budget.reserve(4) is False
    assert budget.used == 0
    assert budget.remaining == 3


def test_settle_releases_unused_reservation() -> None:
    budget = CollectionBudget(10)
    assert budget.reserve(5)
    budget.settle(5, 2)
    assert budget.used == 2
    assert budget.remaining == 8
    assert budget.can_run(8) is True


def test_settle_charges_overrun_beyond_estimate() -> None:
    budget = CollectionBudget(10)
    assert budget.reserve(2)
    budget.settle(2, 6)
    assert budget.used == 6
    assert budget.remaining == 4


def test_settle_reconciles_to_actual_usage() -> None:
    budget = CollectionBudget(10)
    assert budget.reserve(5)
    budget.settle(5, 3)
    assert budget.used == 3
    assert budget.remaining == 7


def test_reserve_rejects_negative_estimate() -> None:
    budget = CollectionBudget(10)
    with pytest.raises(ValueError):
        budget.reserve(-1)
    with pytest.raises(ValueError):
        budget.settle(-1, 1)
    with pytest.raises(ValueError):
        budget.settle(1, -1)


def test_parallel_reservations_never_overshoot_the_cap() -> None:
    budget = CollectionBudget(50)
    errors: list[Exception] = []
    barrier = threading.Barrier(8)

    def worker(amount: int) -> None:
        try:
            barrier.wait()
            budget.reserve(amount)
        except Exception as exc:  # pragma: no cover - unexpected
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(8,)) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors
    assert budget.used <= 50


def test_thread_safe_concurrent_reserve_and_settle() -> None:
    budget = CollectionBudget(10_000)

    def work() -> None:
        budget.reserve(3)
        budget.settle(3, 2)

    threads = [threading.Thread(target=work) for _ in range(200)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert budget.used == 400
    assert budget.remaining == 10_000 - 400
