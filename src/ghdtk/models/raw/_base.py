"""Shared base for raw GitHub data models.

Raw models are immutable source-of-truth snapshots of GitHub API payloads:

- ``frozen=True`` — once deserialized, a raw snapshot cannot be changed.
- ``extra="ignore"`` — unknown payload fields are dropped without raising.
- Optional fields default to ``None`` so missing data is preserved as ``null``
  and never fabricated (e.g. an absent boolean stays ``None``, not ``False``).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BaseRawModel(BaseModel):
    """Base class for every raw GitHub entity."""

    model_config = ConfigDict(frozen=True, extra="ignore")
