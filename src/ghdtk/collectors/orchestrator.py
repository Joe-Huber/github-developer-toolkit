"""Profile collection orchestrator (issue #22).

Schedules the individual collectors by dependency and priority, enforces the
request budget, and aggregates partial success: a run interrupted by a budget
exhaustion or an API failure still returns a :class:`ProfileSnapshot` with an
explicit per-collection status instead of raising.

Sequencing is sequential (concurrency is a deliberate non-goal for now). The
budget planner is :class:`ghdtk.collectors.budget.CollectionBudget`, seeded by
``max_requests``; callers can wire it from
``Settings.collection_max_requests``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial
from typing import TypeVar

from ghdtk.api.client import GitHubClient
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
from ghdtk.models.raw import (
    CollectionRecord,
    CollectionStatus,
    Commit,
    ContributionCalendar,
    Follower,
    Issue,
    LanguageStats,
    ProfileSnapshot,
    PullRequest,
    Readme,
    Repository,
    Stargazer,
    User,
)

__all__ = ["DEFAULT_MAX_REQUESTS", "MAX_COLLECTION_PAGES", "collect_profile"]

DEFAULT_MAX_REQUESTS = 500
MAX_COLLECTION_PAGES = 10

T = TypeVar("T")


def collect_profile(
    client: GitHubClient,
    username: str,
    *,
    max_requests: int | None = None,
    now: datetime | None = None,
) -> ProfileSnapshot:
    """Collect one profile within a request budget.

    Runs the core profile collections first (user, repositories, contribution
    calendar, followers), then per-repository metadata (languages, readme,
    commits, pull requests, issues) for repositories sorted by stars, and
    finally the stargazer timeline for the most-starred owned (non-fork)
    repository, recorded under ``stargazers:<full_name>``. When the budget can no
    longer fit a collection it is skipped with ``reason="budget_exhausted"``;
    when a collection fails the error is recorded and collection continues, so
    the returned snapshot is always complete-but-possibly-partial.
    """
    budget = CollectionBudget(max_requests if max_requests is not None else DEFAULT_MAX_REQUESTS)
    collected_at = now if now is not None else datetime.now(UTC)
    records: list[CollectionRecord] = []

    user: User | None = _run(
        client, budget, records, "user", 1, lambda: collect_user(client, username)
    )

    page_cap = _page_cap(budget)
    repositories: list[Repository] | None = _run(
        client,
        budget,
        records,
        "repositories",
        page_cap,
        lambda: collect_repositories(client, username, max_pages=page_cap),
    )

    calendar: ContributionCalendar | None = _run(
        client,
        budget,
        records,
        "contribution_calendar",
        1,
        lambda: collect_contribution_calendar(client, username),
    )

    page_cap = _page_cap(budget)
    followers: list[Follower] | None = _run(
        client,
        budget,
        records,
        "followers",
        page_cap,
        lambda: collect_followers(client, username, max_pages=page_cap),
    )

    language_stats: dict[str, LanguageStats] = {}
    readmes: dict[str, Readme] = {}
    commits: dict[str, list[Commit]] = {}
    pull_requests: dict[str, list[PullRequest]] = {}
    issues: dict[str, list[Issue]] = {}

    repo_list = repositories if repositories is not None else []
    for repo in sorted(repo_list, key=lambda item: item.stargazers_count or 0, reverse=True):
        full_name = repo.full_name
        if full_name is None or "/" not in full_name:
            continue
        owner, _, repo_name = full_name.partition("/")

        language = _run(
            client,
            budget,
            records,
            f"languages:{full_name}",
            1,
            partial(collect_repo_languages, client, owner, repo_name),
        )
        readme = _run(
            client,
            budget,
            records,
            f"readme:{full_name}",
            1,
            partial(collect_repo_readme, client, owner, repo_name),
        )
        page_cap = _page_cap(budget)
        repo_commits = _run(
            client,
            budget,
            records,
            f"commits:{full_name}",
            page_cap,
            partial(collect_commits, client, owner, repo_name, author=username, max_pages=page_cap),
        )
        page_cap = _page_cap(budget)
        repo_pulls = _run(
            client,
            budget,
            records,
            f"pull_requests:{full_name}",
            page_cap,
            partial(
                collect_pull_requests, client, owner, repo_name, author=username, max_pages=page_cap
            ),
        )
        page_cap = _page_cap(budget)
        repo_issues = _run(
            client,
            budget,
            records,
            f"issues:{full_name}",
            page_cap,
            partial(collect_issues, client, owner, repo_name, author=username, max_pages=page_cap),
        )

        if language is not None:
            language_stats[full_name] = language
        if readme is not None:
            readmes[full_name] = readme
        if repo_commits is not None:
            commits[full_name] = repo_commits
        if repo_pulls is not None:
            pull_requests[full_name] = repo_pulls
        if repo_issues is not None:
            issues[full_name] = repo_issues

    stargazers: list[Stargazer] | None = None
    owned_repo_list = [repo for repo in repo_list if not repo.fork]
    top_repo = max(owned_repo_list, key=lambda item: item.stargazers_count or 0, default=None)
    if top_repo is None or top_repo.full_name is None or "/" not in top_repo.full_name:
        records.append(
            CollectionRecord(
                name="stargazers",
                status=CollectionStatus.SKIPPED,
                reason="no_owned_repositories" if repo_list else "no_repositories",
            )
        )
    else:
        owner, _, repo_name = top_repo.full_name.partition("/")
        page_cap = _page_cap(budget)
        stargazers = _run(
            client,
            budget,
            records,
            f"stargazers:{top_repo.full_name}",
            page_cap,
            lambda: collect_stargazers(client, owner, repo_name, max_pages=page_cap),
        )

    return ProfileSnapshot(
        username=username,
        collected_at=collected_at,
        user=user,
        repositories=repositories,
        languages=language_stats,
        readmes=readmes,
        commits=commits,
        pull_requests=pull_requests,
        issues=issues,
        followers=followers,
        stargazers=stargazers,
        contribution_calendar=calendar,
        collections=records,
        budget_used=budget.used,
        budget_max=budget.max_requests,
    )


def _page_cap(budget: CollectionBudget) -> int:
    """The most pages a paginated collection may use without breaking the cap."""
    return max(1, min(MAX_COLLECTION_PAGES, budget.remaining))


def _run(
    client: GitHubClient,
    budget: CollectionBudget,
    records: list[CollectionRecord],
    name: str,
    estimate: int,
    operation: Callable[[], T],
) -> T | None:
    """Run one collection with budget guarding and status recording."""
    if not budget.can_run(estimate):
        records.append(
            CollectionRecord(
                name=name,
                status=CollectionStatus.SKIPPED,
                reason="budget_exhausted",
            )
        )
        return None
    before = client.requests_made
    try:
        value = operation()
    except Exception as exc:
        used = client.requests_made - before
        budget.consume(used)
        records.append(
            CollectionRecord(
                name=name,
                status=CollectionStatus.FAILED,
                reason=type(exc).__name__,
                detail=str(exc),
                requests_used=used,
            )
        )
        return None
    used = client.requests_made - before
    budget.consume(used)
    records.append(
        CollectionRecord(
            name=name,
            status=CollectionStatus.SUCCESS,
            requests_used=used,
        )
    )
    return value
