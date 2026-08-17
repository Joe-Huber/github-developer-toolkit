"""Tests for ghdtk.observability.metrics (issue #65)."""

from __future__ import annotations

import threading

from ghdtk.observability.metrics import CollectionMetrics, run_timed

# --- CollectionMetrics -----------------------------------------------------


def test_record_timing_accumulates() -> None:
    m = CollectionMetrics()
    m.record_timing("a", 1.0)
    m.record_timing("a", 2.0)
    snap = m.snapshot()
    assert snap["timings"]["a"]["count"] == 2
    assert abs(snap["timings"]["a"]["total_seconds"] - 3.0) < 1e-9


def test_record_timing_mean() -> None:
    m = CollectionMetrics()
    m.record_timing("x", 1.0)
    m.record_timing("x", 3.0)
    assert m.snapshot()["timings"]["x"]["mean_seconds"] == 2.0


def test_record_timing_single_entry() -> None:
    m = CollectionMetrics()
    m.record_timing("s", 0.5)
    snap = m.snapshot()
    assert snap["timings"]["s"]["count"] == 1
    assert snap["timings"]["s"]["mean_seconds"] == 0.5


def test_increment_counter() -> None:
    m = CollectionMetrics()
    m.increment("errors")
    m.increment("errors")
    m.increment("errors", amount=3)
    assert m.snapshot()["counters"]["errors"] == 5


def test_increment_new_counter() -> None:
    m = CollectionMetrics()
    m.increment("new")
    assert m.snapshot()["counters"]["new"] == 1


def test_snapshot_returns_isolated_copy() -> None:
    m = CollectionMetrics()
    m.record_timing("a", 1.0)
    snap1 = m.snapshot()
    m.record_timing("a", 2.0)
    snap2 = m.snapshot()
    assert snap1["timings"]["a"]["total_seconds"] == 1.0
    assert snap2["timings"]["a"]["total_seconds"] == 3.0


def test_snapshot_empty() -> None:
    m = CollectionMetrics()
    snap = m.snapshot()
    assert snap == {"timings": {}, "counters": {}}


def test_snapshot_rounds_seconds() -> None:
    m = CollectionMetrics()
    m.record_timing("t", 0.123456789)
    snap = m.snapshot()
    assert snap["timings"]["t"]["total_seconds"] == 0.123457
    assert snap["timings"]["t"]["mean_seconds"] == 0.123457


def test_snapshot_mean_none_when_empty() -> None:
    """A timing name with count=0 would never appear since we only add on call."""
    m = CollectionMetrics()
    # Manually inject empty _Timing to test the branch
    from ghdtk.observability.metrics import _Timing

    m._timings["empty"] = _Timing()
    snap = m.snapshot()
    assert snap["timings"]["empty"]["count"] == 0
    assert snap["timings"]["empty"]["mean_seconds"] is None


def test_thread_safety_concurrent_record() -> None:
    m = CollectionMetrics()
    n_threads = 16
    n_ops = 200

    def worker() -> None:
        for _ in range(n_ops):
            m.record_timing("t", 0.001)
            m.increment("c")

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    snap = m.snapshot()
    assert snap["timings"]["t"]["count"] == n_threads * n_ops
    assert snap["counters"]["c"] == n_threads * n_ops


# --- run_timed ------------------------------------------------------------


def test_run_timed_records_duration() -> None:
    m = CollectionMetrics()
    result = run_timed(m, "op", lambda: 42)
    assert result == 42
    snap = m.snapshot()
    assert snap["timings"]["op"]["count"] == 1
    assert snap["timings"]["op"]["total_seconds"] >= 0


def test_run_timed_records_on_exception() -> None:
    m = CollectionMetrics()
    try:
        run_timed(m, "err", lambda: (_ for _ in ()).throw(ValueError("bad")))
    except ValueError:
        pass
    snap = m.snapshot()
    assert snap["timings"]["err"]["count"] == 1
    assert snap["timings"]["err"]["total_seconds"] >= 0


def test_run_timed_returns_operation_value() -> None:
    m = CollectionMetrics()
    result = run_timed(m, "r", lambda: [1, 2, 3])
    assert result == [1, 2, 3]
