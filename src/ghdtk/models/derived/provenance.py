"""Provenance for derived analysis data.

Every derived value (metric, score component, finding evidence, recommendation)
carries references to the raw inputs that produced it, so analysis stays
reproducible and explainable.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class SourceEntityKind(StrEnum):
    """The kind of raw entity a derived value references."""

    PROFILE = "profile"
    USER = "user"
    REPOSITORY = "repository"
    README = "readme"
    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    ISSUE = "issue"
    LANGUAGE_STATS = "language_stats"
    STARGAZER = "stargazer"
    CONTRIBUTION_CALENDAR = "contribution_calendar"
    FOLLOWER = "follower"


class SourceReference(BaseModel):
    """A reference to a raw data point that produced a derived value."""

    model_config = ConfigDict(frozen=True)

    entity: SourceEntityKind
    identifier: str
    field: str | None = None
