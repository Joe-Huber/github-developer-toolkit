"""Raw GitHub data models.

Immutable source-of-truth snapshots mirroring the GitHub API payloads. Every
entity the data layer fetches (see issue #16) is represented here; missing
fields stay ``None`` and unknown payload fields are ignored, so payloads can be
deserialized without lossy coercion.

The data layer is deliberately agnostic to the analysis layer: no metric,
score, or recommendation logic lives in these models.
"""

from __future__ import annotations

from ghdtk.models.raw._base import BaseRawModel
from ghdtk.models.raw.commit import (
    Commit,
    CommitDetail,
    CommitParent,
    GitUser,
    Tree,
    Verification,
)
from ghdtk.models.raw.contribution_calendar import (
    ContributionCalendar,
    ContributionDay,
    ContributionWeek,
)
from ghdtk.models.raw.follower import Follower
from ghdtk.models.raw.issue import Issue
from ghdtk.models.raw.issue_shared import Label, Milestone
from ghdtk.models.raw.language_stats import LanguageStats, LanguageStatsContainer
from ghdtk.models.raw.profile import (
    CollectionRecord,
    CollectionStatus,
    ProfileSnapshot,
)
from ghdtk.models.raw.pull_request import PullRequest, PullRequestRef
from ghdtk.models.raw.readme import Readme
from ghdtk.models.raw.repository import License, Repository
from ghdtk.models.raw.stargazer import Stargazer
from ghdtk.models.raw.user import User

__all__ = [
    "BaseRawModel",
    "CollectionRecord",
    "CollectionStatus",
    "Commit",
    "CommitDetail",
    "CommitParent",
    "ContributionCalendar",
    "ContributionDay",
    "ContributionWeek",
    "Follower",
    "GitUser",
    "Issue",
    "Label",
    "LanguageStats",
    "LanguageStatsContainer",
    "License",
    "Milestone",
    "ProfileSnapshot",
    "PullRequest",
    "PullRequestRef",
    "Readme",
    "Repository",
    "Stargazer",
    "Tree",
    "User",
    "Verification",
]
