"""Derived profile summary models (issues #224, #225).

``ProfileIdentity`` forwards the raw ``User`` snapshot fields so the dashboard
can render a profile display page, and ``ProfileTopStats`` rolls headline
numbers computed from already-collected raw data into a small, provenance-backed
summary. Both are derived from the raw snapshot by
:mod:`ghdtk.analyzers.profile_summary` and never fetch new data.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ghdtk.models.derived.metric import MetricAvailability, MetricRecord
from ghdtk.models.derived.provenance import SourceReference

__all__ = [
    "ProfileIdentity",
    "ProfileTopStats",
    "TopLanguage",
    "TopRepository",
]


class ProfileIdentity(BaseModel):
    """Profile identity fields copied from the raw ``User`` snapshot.

    Every field is ``None`` when GitHub did not provide it; ``availability`` is
    ``MetricAvailability.UNAVAILABLE`` when no ``User`` snapshot exists at all.
    """

    model_config = ConfigDict(frozen=True)

    username: str
    name: str | None = None
    avatar_url: str | None = None
    html_url: str | None = None
    bio: str | None = None
    company: str | None = None
    blog: str | None = None
    location: str | None = None
    email: str | None = None
    twitter_username: str | None = None
    hireable: bool | None = None
    public_repos: int | None = None
    public_gists: int | None = None
    followers: int | None = None
    following: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    availability: MetricAvailability = MetricAvailability.AVAILABLE


class TopRepository(BaseModel):
    """A repository surfaced as a headline top stat."""

    model_config = ConfigDict(frozen=True)

    name: str
    full_name: str
    stargazers_count: int = 0
    description: str | None = None
    html_url: str | None = None
    language: str | None = None


class TopLanguage(BaseModel):
    """One language's share of the profile's byte-weighted code distribution."""

    model_config = ConfigDict(frozen=True)

    language: str
    bytes: int
    share: float


class ProfileTopStats(BaseModel):
    """Headline statistics for the profile display page.

    ``metrics`` are full :class:`~ghdtk.models.derived.MetricRecord` values so
    each stat carries its provenance and honest availability, while
    ``top_repositories`` and ``top_languages`` add the structured extras the
    frontend needs to render list sections.
    """

    model_config = ConfigDict(frozen=True)

    username: str
    metrics: list[MetricRecord] = Field(default_factory=list)
    top_repositories: list[TopRepository] = Field(default_factory=list)
    top_languages: list[TopLanguage] = Field(default_factory=list)
    sources: list[SourceReference] = Field(default_factory=list)
    availability: MetricAvailability = MetricAvailability.AVAILABLE
