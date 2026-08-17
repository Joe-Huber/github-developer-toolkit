"""Structured, correlation-tagged logging (issue #65).

Collection runs emit structured log events: every line is a single JSON object
carrying a correlation id, timestamp, level, logger name, message and the
caller-supplied structured fields, so a failed run can be traced end to end
and replayed with tools that understand newline-delimited JSON.

Correlation ids are tracked in a :mod:`contextvars` context: a run opened with
:func:`run_correlation` tags every log line it emits (including lines from
worker threads, which inherit the context). Events follow a small vocabulary:

- ``collection.run.start`` / ``collection.run.end`` — one per ``collect_profile``
  call, with the budget, wall-clock time, per-status tallies and request counts.
- ``collection.<name>.start`` / ``collection.<name>.end`` — one per collection,
  with the measured duration and requests used, plus ``error`` on failure.

The module is intentionally dependency-free beyond the stdlib; formatting is
JSON via :class:`StructuredFormatter`.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, TextIO

__all__ = [
    "StructuredFormatter",
    "configure_logging",
    "get_correlation_id",
    "new_correlation_id",
    "run_correlation",
]

_LOG_FORMAT = "%(asctime)s.%(msecs)03dZ"
_LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

_CORRELATION_ID: ContextVar[str] = ContextVar("correlation_id", default="")

# stdlib LogRecord attributes we never want to leak into structured output.
_RESERVED_FIELDS = frozenset(
    {
        "args",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


def new_correlation_id() -> str:
    """Return a fresh correlation id for a collection run."""
    return uuid.uuid4().hex


def get_correlation_id() -> str:
    """Return the correlation id active in the current context (may be empty)."""
    return _CORRELATION_ID.get()


class run_correlation:
    """Context manager scoping a correlation id to a block of code.

    Every structured log emitted inside the block (including from worker
    threads) carries the id. The previous id is restored on exit so nested
    runs do not leak their tag into the caller.
    """

    def __init__(self, correlation_id: str | None = None) -> None:
        self.correlation_id = correlation_id or new_correlation_id()
        self._token: Any | None = None

    def __enter__(self) -> str:
        self._token = _CORRELATION_ID.set(self.correlation_id)
        return self.correlation_id

    def __exit__(self, *exc: object) -> None:
        if self._token is not None:
            _CORRELATION_ID.reset(self._token)


class StructuredFormatter(logging.Formatter):
    """Format records as single-line JSON with a correlation tag."""

    def __init__(self) -> None:
        super().__init__(fmt=_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds")
        payload: dict[str, Any] = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "correlation_id": get_correlation_id(),
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_FIELDS and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO, *, stream: TextIO | None = None) -> None:
    """Attach the structured formatter to the ``ghdtk`` logger at ``level``.

    Idempotent: a second call replaces the previous handler on the
    ``ghdtk`` logger rather than stacking duplicates. ``stream`` defaults to
    standard error.
    """
    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.setFormatter(StructuredFormatter())
    logger = logging.getLogger("ghdtk")
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Return the ``ghdtk.<name>`` logger for structured collection events."""
    return logging.getLogger(f"ghdtk.{name}")
