"""Profile README retrieval artifact (issue #25).

The profile README lives in the ``username/username`` repository. This model
captures the retrieval outcome with distinct typed states so downstream
analysis can tell "no profile repository" from "repository without a README",
"empty README", and "fetch failed" apart. Like :class:`ProfileSnapshot`, it is
a collection artifact rather than a single GitHub API payload.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ProfileReadmeStatus(StrEnum):
    """Outcome of a profile README retrieval attempt."""

    PRESENT = "present"
    NO_PROFILE_REPO = "no_profile_repo"
    NO_README = "no_readme"
    EMPTY = "empty"
    FETCH_FAILED = "fetch_failed"


class ProfileReadme(BaseModel):
    """The profile README artifact or a typed reason for its absence."""

    model_config = ConfigDict(frozen=True)

    username: str
    status: ProfileReadmeStatus
    content: str | None = None
    repository: str | None = None
    reason: str | None = None


__all__ = ["ProfileReadme", "ProfileReadmeStatus"]
