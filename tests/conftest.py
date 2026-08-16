"""Shared test fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

sys.path.insert(0, str(FIXTURES_DIR))


@pytest.fixture
def load_raw_fixture() -> Any:
    """Return a callable that loads a raw JSON fixture as a dict."""

    def _load(name: str) -> Any:
        path = FIXTURES_DIR / "raw" / f"{name}.json"
        with path.open() as handle:
            return json.load(handle)

    return _load
