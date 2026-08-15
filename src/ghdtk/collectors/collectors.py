"""Individual collectors scheduled by the orchestrator (issue #22).

Each function performs exactly one collection and returns raw typed data (or
``None`` when the resource is legitimately absent). The orchestrator owns
budgeting, ordering and failure handling; these stay thin so any future
collector reuses the same data layer instead of bespoke HTTP calls.
"""

from __future__ import annotations

from collections.abc import Sequence

from ghdtk.api.client import GitHubClient
from ghdtk.api.errors import GitHubAPIError
from ghdtk.models.raw import (
    Commit,
    ContributionCalendar,
    Follower,
    Issue,
    LanguageStats,
    ProfileReadme,
    ProfileReadmeStatus,
    PullRequest,
    Readme,
    Repository,
    Stargazer,
    User,
)

__all__ = [
    "collect_commits",
    "collect_contribution_calendar",
    "collect_followers",
    "collect_issues",
    "collect_profile_readme",
    "collect_pull_requests",
    "collect_repo_languages",
    "collect_repo_readme",
    "collect_repositories",
    "collect_stargazers",
    "collect_user",
]


def collect_user(client: GitHubClient, username: str) -> User:
    """Collect the profile's core user record."""
    return client.get_user(username)


def collect_repositories(
    client: GitHubClient,
    username: str,
    *,
    max_pages: int = 10,
) -> list[Repository]:
    """Collect every repository of the profile (paginated)."""
    return client.list_user_repositories(username, max_pages=max_pages)


def collect_repo_languages(
    client: GitHubClient,
    owner: str,
    repo: str,
) -> LanguageStats:
    """Collect the language breakdown for one repository."""
    return client.get_languages(owner, repo)


def collect_repo_readme(
    client: GitHubClient,
    owner: str,
    repo: str,
) -> Readme | None:
    """Collect a repository README, or ``None`` when the repo has none."""
    return client.get_readme(owner, repo)


def collect_profile_readme(
    client: GitHubClient,
    username: str,
    *,
    repositories: Sequence[Repository] | None = None,
    max_pages: int = 1,
) -> ProfileReadme:
    """Collect the profile README with distinct absent/empty/failure states.

    The profile README lives in the ``<username>/<username>`` repository. Pass
    the repositories already collected for the profile to avoid an extra
    request; otherwise a bounded fetch is performed first. The result is a
    typed :class:`ProfileReadme` so analysis can tell "no profile repository"
    from "repository without a README", "empty README", or a fetch failure.
    """
    if repositories is None:
        repositories = client.list_user_repositories(username, max_pages=max_pages)
    profile_repo = next(
        (
            repo
            for repo in repositories
            if (repo.name or "").lower() == username.lower()
            or (repo.full_name or "").lower() == f"{username}/{username}".lower()
        ),
        None,
    )
    if profile_repo is None:
        return ProfileReadme(username=username, status=ProfileReadmeStatus.NO_PROFILE_REPO)
    try:
        readme = client.get_readme(username, username)
    except GitHubAPIError as exc:
        return ProfileReadme(
            username=username,
            status=ProfileReadmeStatus.FETCH_FAILED,
            reason=str(exc),
        )
    if readme is None:
        return ProfileReadme(username=username, status=ProfileReadmeStatus.NO_README)
    content = readme.decoded_content or ""
    if not content.strip():
        return ProfileReadme(username=username, status=ProfileReadmeStatus.EMPTY)
    return ProfileReadme(
        username=username,
        status=ProfileReadmeStatus.PRESENT,
        content=content,
        repository=f"{username}/{username}",
    )


def collect_commits(
    client: GitHubClient,
    owner: str,
    repo: str,
    *,
    author: str,
    max_pages: int = 10,
) -> list[Commit]:
    """Collect the author's commits in one repository (paginated)."""
    return client.list_commits(owner, repo, author=author, max_pages=max_pages)


def collect_pull_requests(
    client: GitHubClient,
    owner: str,
    repo: str,
    *,
    author: str,
    max_pages: int = 10,
) -> list[PullRequest]:
    """Collect the author's pull requests in one repository (paginated)."""
    return client.list_pull_requests(owner, repo, max_pages=max_pages)


def collect_issues(
    client: GitHubClient,
    owner: str,
    repo: str,
    *,
    author: str,
    max_pages: int = 10,
) -> list[Issue]:
    """Collect the author's issues in one repository (paginated)."""
    return client.list_issues(owner, repo, max_pages=max_pages)


def collect_followers(
    client: GitHubClient,
    username: str,
    *,
    max_pages: int = 10,
) -> list[Follower]:
    """Collect the profile's followers (paginated)."""
    return client.list_followers(username, max_pages=max_pages)


def collect_following(
    client: GitHubClient,
    username: str,
    *,
    max_pages: int = 10,
) -> list[Follower]:
    """Collect the profile's following list (paginated)."""
    return client.list_following(username, max_pages=max_pages)


def collect_stargazers(
    client: GitHubClient,
    owner: str,
    repo: str,
    *,
    max_pages: int = 10,
) -> list[Stargazer]:
    """Collect the stargazers of one repository (paginated)."""
    return client.list_stargazers(owner, repo, max_pages=max_pages)


def collect_contribution_calendar(
    client: GitHubClient,
    username: str,
) -> ContributionCalendar:
    """Collect the profile's GraphQL contribution calendar."""
    return client.get_contribution_calendar(username)
