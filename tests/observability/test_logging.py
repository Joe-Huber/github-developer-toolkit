"""Tests for ghdtk.observability.logging (issue #65)."""

from __future__ import annotations

import io
import json
import logging
from concurrent.futures import ThreadPoolExecutor

import pytest

from ghdtk.observability.logging import (
    StructuredFormatter,
    configure_logging,
    get_correlation_id,
    get_logger,
    new_correlation_id,
    run_correlation,
)

# --- helpers ---------------------------------------------------------------


def _emit(logger: logging.Logger, msg: str = "test", **extra: object) -> None:
    logger.info(msg, extra=extra)


def _last_json(stream: io.StringIO) -> dict[str, object]:
    stream.seek(0)
    for _line in stream:
        pass
    result: dict[str, object] = json.loads(_line)
    return result


def _all_json(stream: io.StringIO) -> list[dict[str, object]]:
    stream.seek(0)
    result: list[dict[str, object]] = [json.loads(line) for line in stream if line.strip()]
    return result


# --- new_correlation_id / get_correlation_id ------------------------------


def test_new_correlation_id_is_32_hex() -> None:
    cid = new_correlation_id()
    assert len(cid) == 32
    int(cid, 16)  # must parse as hex


def test_get_correlation_id_default_empty() -> None:
    assert get_correlation_id() == ""


# --- run_correlation ------------------------------------------------------


def test_run_correlation_sets_and_restores() -> None:
    cid = "deadbeef"
    with run_correlation(cid) as returned:
        assert returned == cid
        assert get_correlation_id() == cid
    assert get_correlation_id() == ""


def test_run_correlation_auto_generates_id() -> None:
    with run_correlation() as cid:
        assert len(cid) == 32
        assert get_correlation_id() == cid


def test_nested_run_correlation_restores_outer() -> None:
    with run_correlation("outer"):
        assert get_correlation_id() == "outer"
        with run_correlation("inner"):
            assert get_correlation_id() == "inner"
        assert get_correlation_id() == "outer"
    assert get_correlation_id() == ""


def test_correlation_id_explicit_thread_propagation() -> None:
    """Verify that explicitly setting run_correlation in a worker thread works.

    Python < 3.12 does NOT propagate contextvars to threads automatically.
    The orchestrator passes the correlation_id explicitly and wraps each
    worker function in run_correlation(correlation_id) to set it.
    """
    inherited: list[str] = []
    with run_correlation("ctx-123"):
        captured = get_correlation_id()
        with ThreadPoolExecutor(max_workers=1) as pool:

            def _worker() -> None:
                with run_correlation(captured):
                    inherited.append(get_correlation_id())

            pool.submit(_worker).result()
    assert inherited == ["ctx-123"]


def test_run_correlation_restores_after_exception() -> None:
    with pytest.raises(RuntimeError):
        with run_correlation("test-id"):
            raise RuntimeError("boom")
    assert get_correlation_id() == ""


# --- StructuredFormatter --------------------------------------------------


def test_format_json_shape() -> None:
    fmt = StructuredFormatter()
    record = logging.LogRecord(
        name="ghdtk.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    line = fmt.format(record)
    data = json.loads(line)
    assert data["message"] == "hello world"
    assert data["level"] == "INFO"
    assert data["logger"] == "ghdtk.test"
    assert "ts" in data
    assert "correlation_id" in data


def test_format_includes_extra_fields() -> None:
    fmt = StructuredFormatter()
    record = logging.LogRecord(
        name="ghdtk.test",
        level=logging.WARNING,
        pathname="test.py",
        lineno=1,
        msg="done",
        args=(),
        exc_info=None,
    )
    record.collection = "user"
    record.requests_used = 3
    data = json.loads(fmt.format(record))
    assert data["collection"] == "user"
    assert data["requests_used"] == 3


def test_format_excludes_reserved_fields() -> None:
    fmt = StructuredFormatter()
    record = logging.LogRecord(
        name="ghdtk.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="ok",
        args=(),
        exc_info=None,
    )
    line = fmt.format(record)
    data = json.loads(line)
    for reserved in (
        "args",
        "created",
        "exc_info",
        "filename",
        "module",
        "msecs",
        "process",
        "thread",
        "threadName",
    ):
        assert reserved not in data, f"{reserved} leaked into output"


def test_format_includes_exception_info() -> None:
    fmt = StructuredFormatter()
    try:
        raise ValueError("bad")
    except ValueError:
        import sys

        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name="ghdtk.test",
        level=logging.ERROR,
        pathname="test.py",
        lineno=1,
        msg="fail",
        args=(),
        exc_info=exc_info,
    )
    data = json.loads(fmt.format(record))
    assert "exc_info" in data
    assert "ValueError: bad" in data["exc_info"]


def test_format_correlation_id_from_context() -> None:
    fmt = StructuredFormatter()
    with run_correlation("abc-123"):
        record = logging.LogRecord(
            name="ghdtk.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="tagged",
            args=(),
            exc_info=None,
        )
        data = json.loads(fmt.format(record))
        assert data["correlation_id"] == "abc-123"


# --- configure_logging ----------------------------------------------------


def test_configure_logging_idempotent() -> None:
    stream1 = io.StringIO()
    stream2 = io.StringIO()
    configure_logging(level=logging.DEBUG, stream=stream1)
    logger = logging.getLogger("ghdtk")
    assert len(logger.handlers) == 1
    configure_logging(level=logging.WARNING, stream=stream2)
    assert len(logger.handlers) == 1
    assert logger.level == logging.WARNING


def test_configure_logging_default_stderr() -> None:
    configure_logging()
    logger = logging.getLogger("ghdtk")
    assert len(logger.handlers) == 1
    handler = logger.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is not None


def test_configure_logging_propagate_false() -> None:
    configure_logging()
    logger = logging.getLogger("ghdtk")
    assert logger.propagate is False


def test_configure_logging_custom_stream_captures_output() -> None:
    stream = io.StringIO()
    configure_logging(level=logging.DEBUG, stream=stream)
    log = get_logger("test")
    _emit(log, "hello")
    data = _last_json(stream)
    assert data["message"] == "hello"
    assert data["logger"] == "ghdtk.test"


# --- get_logger -----------------------------------------------------------


def test_get_logger_prefix() -> None:
    log = get_logger("collectors")
    assert log.name == "ghdtk.collectors"
