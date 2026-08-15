"""Profile collection snapshot model.

``ProfileSnapshot`` is the container produced by the collection orchestrator
(issue #22): every collection the pipeline attempted plus its status, so a run
interrupted by rate limits returns a complete-but-partial result with explicit
missing/unavailable markers instead of crashing. Unlike the raw entity models,
it is a collection container rather than a single API payload.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ghdtk.models.raw.commit import Commit
from ghdtk.models.raw.contribution_calendar import ContributionCalendar
from ghdtk.models.raw.follower import Follower
from ghdtk.models.raw.issue import Issue
from ghdtk.models.raw.language_stats import LanguageStats
from ghdtk.models.raw.pull_request import PullRequest
from ghdtk.models.raw.readme import Readme
from ghdtk.models.raw.repository import Repository
from ghdtk.models.raw.stargazer import Stargazer
from ghdtk.models.raw.user import User


class CollectionStatus(StrEnum):
    """Outcome of one collection in the pipeline."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


class CollectionRecord(BaseModel):
    """Status of one collection attempt."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: CollectionStatus
    reason: str | None = None
    detail: str | None = None
    requests_used: int = 0


class ProfileSnapshot(BaseModel):
    """What a single collection run gathered for one GitHub profile."""

    model_config = ConfigDict(frozen=True)

    username: str
    collected_at: datetime
    user: User | None = None
    repositories: list[Repository] | None = None
    languages: dict[str, LanguageStats] = Field(default_factory=dict)
    readmes: dict[str, Readme] = Field(default_factory=dict)
    commits: dict[str, list[Commit]] = Field(default_factory=dict)
    pull_requests: dict[str, list[PullRequest]] = Field(default_factory=dict)
    issues: dict[str, list[Issue]] = Field(default_factory=dict)
    followers: list[Follower] | None = None
    following: list[Follower] | None = None
    stargazers: list[Stargazer] | None = None
    contribution_calendar: ContributionCalendar | None = None
    collections: list[CollectionRecord] = Field(default_factory=list)
    budget_used: int = 0
    budget_max: int = 0

    @property
    def is_partial(self) -> bool:
        """Whether any collection failed, was skipped, or never completed."""
        return any(record.status != CollectionStatus.SUCCESS for record in self.collections)


__all__ = [
    "CollectionRecord",
    "CollectionStatus",
    "ProfileSnapshot",
]
