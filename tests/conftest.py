"""Shared test fixtures."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

sys.path.insert(0, str(FIXTURES_DIR))


@pytest.fixture(autouse=True)
def _reset_ghdtk_logger() -> Any:
    """Reset the ``ghdtk`` logger after each test.

    Tests that call :func:`~ghdtk.observability.configure_logging` attach a
    handler and set ``propagate = False`` on the ``ghdtk`` logger.  If those
    changes leak into subsequent tests, pytest's captured stderr stream is
    already closed, causing ``ValueError: I/O operation on closed file``.
    """
    yield
    logger = logging.getLogger("ghdtk")
    logger.handlers.clear()
    logger.propagate = True
    logger.setLevel(logging.WARNING)


@pytest.fixture
def load_raw_fixture() -> Any:
    """Return a callable that loads a raw JSON fixture as a dict."""

    def _load(name: str) -> Any:
        path = FIXTURES_DIR / "raw" / f"{name}.json"
        with path.open() as handle:
            return json.load(handle)

    return _load
