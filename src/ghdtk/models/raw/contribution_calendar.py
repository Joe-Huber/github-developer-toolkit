"""Raw GitHub contribution calendar model.

Mirrors the contribution calendar returned by the GraphQL API
(``contributionCalendar`` on ``user``). GraphQL field names are camelCase, so
the models alias ``totalContributions``, ``contributionDays`` and friends while
also accepting the snake_case field names.
"""

from __future__ import annotations

import datetime

from pydantic import ConfigDict
from pydantic.alias_generators import to_camel

from ghdtk.models.raw._base import BaseRawModel


class ContributionDay(BaseRawModel):
    """A single day of the contribution calendar."""

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
        alias_generator=to_camel,
        populate_by_name=True,
    )

    color: str | None = None
    contribution_count: int | None = None
    date: datetime.date | None = None
    weekday: int | None = None


class ContributionWeek(BaseRawModel):
    """A week of the contribution calendar."""

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
        alias_generator=to_camel,
        populate_by_name=True,
    )

    first_day: datetime.date | None = None
    contribution_days: list[ContributionDay] | None = None


class ContributionCalendar(BaseRawModel):
    """The contribution calendar of a GitHub user."""

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
        alias_generator=to_camel,
        populate_by_name=True,
    )

    total_contributions: int | None = None
    weeks: list[ContributionWeek] | None = None
