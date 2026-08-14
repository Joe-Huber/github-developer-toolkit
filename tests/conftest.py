"""Shared test fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_raw_fixture() -> Any:
    """Return a callable that loads a raw JSON fixture as a dict."""

    def _load(name: str) -> Any:
        path = FIXTURES_DIR / "raw" / f"{name}.json"
        with path.open() as handle:
            return json.load(handle)

    return _load
