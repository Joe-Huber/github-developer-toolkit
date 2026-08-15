"""Profile collection pipeline (issue #22).

Collectors fetch GitHub data through the typed client and return raw typed
payloads; the orchestrator (:func:`collect_profile`) schedules them within a
request budget and aggregates partial success into a
:class:`~ghdtk.models.raw.ProfileSnapshot`.
"""

from __future__ import annotations

from ghdtk.collectors.budget import CollectionBudget
from ghdtk.collectors.collectors import (
    collect_commits,
    collect_contribution_calendar,
    collect_followers,
    collect_issues,
    collect_pull_requests,
    collect_repo_languages,
    collect_repo_readme,
    collect_repositories,
    collect_stargazers,
    collect_user,
)
from ghdtk.collectors.orchestrator import DEFAULT_MAX_REQUESTS, collect_profile

__all__ = [
    "DEFAULT_MAX_REQUESTS",
    "CollectionBudget",
    "collect_commits",
    "collect_contribution_calendar",
    "collect_followers",
    "collect_issues",
    "collect_profile",
    "collect_pull_requests",
    "collect_repo_languages",
    "collect_repo_readme",
    "collect_repositories",
    "collect_stargazers",
    "collect_user",
]
