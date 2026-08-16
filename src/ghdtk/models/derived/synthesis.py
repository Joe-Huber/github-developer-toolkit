"""Derived synthesis model.

The synthesis assembles the full assessment into the sections a report renders:
strengths, weaknesses, red flags for missing or possibly misleading
information, and a prioritized improvement plan.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ghdtk.models.derived.recommendation import Recommendation


class Synthesis(BaseModel):
    """One profile's synthesized assessment."""

    model_config = ConfigDict(frozen=True)

    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    plan: list[Recommendation] = Field(default_factory=list)
