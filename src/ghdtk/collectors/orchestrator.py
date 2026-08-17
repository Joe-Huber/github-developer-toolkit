"""Profile collection orchestrator (issue #22).

Schedules the individual collectors by dependency and priority, enforces the
request budget, and aggregates partial success: a run interrupted by a budget
exhaustion or an API failure still returns a :class:`ProfileSnapshot` with an
explicit per-collection status instead of raising.

The per-repository metadata phase can run concurrently (issue #63): each
repository group is *reserved* against the shared budget before it is
dispatched, so parallel bursts are accounted for up front and the run can never
exceed ``max_requests``. The budget planner is
:class:`ghdtk.collectors.budget.CollectionBudget`, seeded by ``max_requests``;
callers can wire it from ``Settings.collection_max_requests``. Collection
progress, per-collection timing and failures are logged through the
:mod:`ghdtk.observability` module (issue #65).
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from functools import partial
from time import perf_counter
from typing import TypeVar

from ghdtk.api.client import GitHubClient
from ghdtk.collectors.budget import CollectionBudget
from ghdtk.collectors.collectors import (
    collect_commits,
    collect_contribution_calendar,
    collect_followers,
    collect_following,
    collect_issue_search,
    collect_issues,
    collect_pull_request_search,
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
from ghdtk.observability import (
    CollectionMetrics,
    get_correlation_id,
    get_logger,
    run_correlation,
)

__all__ = ["DEFAULT_MAX_REQUESTS", "MAX_COLLECTION_PAGES", "collect_profile"]

DEFAULT_MAX_REQUESTS = 500
MAX_COLLECTION_PAGES = 10
MAX_WORKERS_LIMIT = 32

T = TypeVar("T")

_logger = get_logger("collectors")


def collect_profile(
    client: GitHubClient,
    username: str,
    *,
    max_requests: int | None = None,
    now: datetime | None = None,
    max_workers: int = 1,
) -> ProfileSnapshot:
    """Collect one profile within a request budget.

    Runs the core profile collections first (user, repositories, contribution
    calendar, followers, following), then cross-repository PR and issue
    collections via the search API (``pull_requests:search``,
    ``issues:search``), then per-repository metadata (languages, readme,
    commits, pull requests, issues) for repositories sorted by stars, and
    finally the stargazer timeline for the most-starred owned (non-fork)
    repository, recorded under ``stargazers:<full_name>``. When the budget can no
    longer fit a collection it is skipped with ``reason="budget_exhausted"``;
    when a collection fails the error is recorded and collection continues, so
    the returned snapshot is always complete-but-possibly-partial.

    ``max_workers`` controls parallelism for the per-repository metadata phase
    (issue #63): the default of ``1`` keeps the pipeline strictly sequential
    and deterministic, while a value above ``1`` runs the per-repository
    collectors in a thread pool. The request budget is shared, and each
    repository group is *reserved* against the budget before it is dispatched,
    so parallel bursts are accounted for up front and the run can never exceed
    ``max_requests``. ``max_workers=1`` and ``max_workers>1`` produce identical
    snapshots whenever the budget fits every collection.

    Every run emits structured, correlation-tagged logs and a
    :class:`CollectionMetrics` snapshot (issue #65): a correlation id is scoped
    for the call, each collection logs its start/end, duration and request
    usage, failures log the error, and the final run summary tallies statuses,
    budget usage and per-collection timings so a failed run is actionable.
    """
    metrics = CollectionMetrics()
    with run_correlation() as correlation_id:
        _logger.info(
            "collection.run.start",
            extra={
                "correlation_id": correlation_id,
                "username": username,
                "budget_max": max_requests if max_requests is not None else DEFAULT_MAX_REQUESTS,
                "max_workers": max_workers,
            },
        )
        snapshot = _collect(
            client,
            username,
            budget_max=max_requests if max_requests is not None else DEFAULT_MAX_REQUESTS,
            now=now,
            max_workers=max_workers,
            metrics=metrics,
        )
        colls = snapshot.collections
        _logger.info(
            "collection.run.end",
            extra={
                "correlation_id": correlation_id,
                "username": username,
                "budget_used": snapshot.budget_used,
                "budget_max": snapshot.budget_max,
                "collections_total": len(colls),
                "collections_succeeded": sum(
                    1 for r in colls if r.status == CollectionStatus.SUCCESS
                ),
                "collections_skipped": sum(
                    1 for r in colls if r.status == CollectionStatus.SKIPPED
                ),
                "collections_failed": sum(1 for r in colls if r.status == CollectionStatus.FAILED),
                "metrics": metrics.snapshot(),
            },
        )
        return snapshot


def _collect(
    client: GitHubClient,
    username: str,
    *,
    budget_max: int,
    now: datetime | None,
    max_workers: int,
    metrics: CollectionMetrics,
) -> ProfileSnapshot:
    """The actual collection pipeline (split out for run-level observability)."""
    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")
    if max_workers > MAX_WORKERS_LIMIT:
        raise ValueError(f"max_workers must be at most {MAX_WORKERS_LIMIT}")
    budget = CollectionBudget(budget_max)
    collected_at = now if now is not None else datetime.now(UTC)
    records: list[CollectionRecord] = []

    _logger.debug(
        "collection.mode",
        extra={"mode": "parallel" if max_workers > 1 else "sequential", "max_workers": max_workers},
    )

    user: User | None = _run(
        client, budget, records, "user", 1, lambda: collect_user(client, username), metrics=metrics
    )

    page_cap = _page_cap(budget)
    repositories: list[Repository] | None = _run(
        client,
        budget,
        records,
        "repositories",
        page_cap,
        lambda: collect_repositories(client, username, max_pages=page_cap),
        metrics=metrics,
    )

    calendar: ContributionCalendar | None = _run(
        client,
        budget,
        records,
        "contribution_calendar",
        1,
        lambda: collect_contribution_calendar(client, username),
        metrics=metrics,
    )

    page_cap = _page_cap(budget)
    followers: list[Follower] | None = _run(
        client,
        budget,
        records,
        "followers",
        page_cap,
        lambda: collect_followers(client, username, max_pages=page_cap),
        metrics=metrics,
    )

    page_cap = _page_cap(budget)
    following: list[Follower] | None = _run(
        client,
        budget,
        records,
        f"following:{username}",
        page_cap,
        lambda: collect_following(client, username, max_pages=page_cap),
        metrics=metrics,
    )

    page_cap = _page_cap(budget)
    search_pull_requests: list[PullRequest] | None = _run(
        client,
        budget,
        records,
        "pull_requests:search",
        page_cap,
        lambda: collect_pull_request_search(client, username, max_pages=page_cap),
        metrics=metrics,
    )

    page_cap = _page_cap(budget)
    search_issues: list[Issue] | None = _run(
        client,
        budget,
        records,
        "issues:search",
        page_cap,
        lambda: collect_issue_search(client, username, max_pages=page_cap),
        metrics=metrics,
    )

    language_stats: dict[str, LanguageStats] = {}
    readmes: dict[str, Readme] = {}
    commits: dict[str, list[Commit]] = {}
    pull_requests: dict[str, list[PullRequest]] = {}
    issues: dict[str, list[Issue]] = {}

    repo_list = repositories if repositories is not None else []
    sorted_repos = sorted(repo_list, key=lambda item: item.stargazers_count or 0, reverse=True)

    if max_workers > 1:
        _collect_repo_metadata_parallel(
            client,
            budget,
            records,
            sorted_repos,
            username,
            language_stats,
            readmes,
            commits,
            pull_requests,
            issues,
            max_workers=max_workers,
            metrics=metrics,
        )
    else:
        for repo in sorted_repos:
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
                metrics=metrics,
            )
            readme = _run(
                client,
                budget,
                records,
                f"readme:{full_name}",
                1,
                partial(collect_repo_readme, client, owner, repo_name),
                metrics=metrics,
            )
            page_cap = _page_cap(budget)
            repo_commits = _run(
                client,
                budget,
                records,
                f"commits:{full_name}",
                page_cap,
                partial(
                    collect_commits, client, owner, repo_name, author=username, max_pages=page_cap
                ),
                metrics=metrics,
            )
            page_cap = _page_cap(budget)
            repo_pulls = _run(
                client,
                budget,
                records,
                f"pull_requests:{full_name}",
                page_cap,
                partial(
                    collect_pull_requests,
                    client,
                    owner,
                    repo_name,
                    author=username,
                    max_pages=page_cap,
                ),
                metrics=metrics,
            )
            page_cap = _page_cap(budget)
            repo_issues = _run(
                client,
                budget,
                records,
                f"issues:{full_name}",
                page_cap,
                partial(
                    collect_issues, client, owner, repo_name, author=username, max_pages=page_cap
                ),
                metrics=metrics,
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
            metrics=metrics,
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
        search_pull_requests=search_pull_requests if search_pull_requests is not None else [],
        search_issues=search_issues if search_issues is not None else [],
        followers=followers,
        following=following,
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
    *,
    metrics: CollectionMetrics,
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
        _logger.info(
            "collection.skipped",
            extra={"collection": name, "reason": "budget_exhausted"},
        )
        return None
    _logger.debug("collection.start", extra={"collection": name})
    before = client.requests_made
    started = perf_counter()
    try:
        value = operation()
    except Exception as exc:
        used = client.requests_made - before
        duration = perf_counter() - started
        metrics.record_timing(name, duration)
        metrics.increment("errors")
        metrics.increment(f"errors:{name}")
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
        _logger.warning(
            "collection.failed",
            extra={
                "collection": name,
                "error": type(exc).__name__,
                "detail": str(exc),
                "requests_used": used,
                "duration_seconds": round(duration, 6),
            },
        )
        return None
    used = client.requests_made - before
    duration = perf_counter() - started
    metrics.record_timing(name, duration)
    budget.consume(used)
    records.append(
        CollectionRecord(
            name=name,
            status=CollectionStatus.SUCCESS,
            requests_used=used,
        )
    )
    _logger.info(
        "collection.end",
        extra={
            "collection": name,
            "requests_used": used,
            "duration_seconds": round(duration, 6),
        },
    )
    return value


def _collect_repo_metadata_parallel(
    client: GitHubClient,
    budget: CollectionBudget,
    records: list[CollectionRecord],
    sorted_repos: list[Repository],
    username: str,
    language_stats: dict[str, LanguageStats],
    readmes: dict[str, Readme],
    commits: dict[str, list[Commit]],
    pull_requests: dict[str, list[PullRequest]],
    issues: dict[str, list[Issue]],
    *,
    max_workers: int,
    metrics: CollectionMetrics,
) -> None:
    """Run the per-repository metadata phase concurrently (issue #63).

    Every repository group (languages, readme, commits, pull requests, issues)
    is *reserved* against the shared budget before it is dispatched, so the
    planner sees the worst-case cost of each parallel burst up front and can
    refuse groups that would exceed ``max_requests``. Groups that fit run in a
    thread pool; the per-repository records are merged back in star order so
    the snapshot is byte-identical to the sequential run whenever the budget
    fits everything.
    """
    plan: list[tuple[Repository, str, int, int]] = []
    for repo in sorted_repos:
        full_name = repo.full_name
        if full_name is None or "/" not in full_name:
            continue
        page_cap = _page_cap(budget)
        # 1 request each for languages/readme + page_cap each for the rest.
        group_estimate = 2 + 3 * page_cap
        if not budget.reserve(group_estimate):
            for name in (
                "languages",
                "readme",
                "commits",
                "pull_requests",
                "issues",
            ):
                records.append(
                    CollectionRecord(
                        name=f"{name}:{full_name}",
                        status=CollectionStatus.SKIPPED,
                        reason="budget_exhausted",
                    )
                )
                _logger.info(
                    "collection.skipped",
                    extra={"collection": f"{name}:{full_name}", "reason": "budget_exhausted"},
                )
            continue
        plan.append((repo, full_name, page_cap, group_estimate))

    if not plan:
        return

    correlation_id = get_correlation_id()
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ghdtk-collect") as pool:
        submitted = [
            (
                index,
                pool.submit(
                    _collect_repo_group,
                    client,
                    username,
                    repo,
                    page_cap,
                    metrics,
                    correlation_id,
                ),
            )
            for index, (repo, _full_name, page_cap, _estimate) in enumerate(plan)
        ]

        for index, future in sorted(submitted, key=lambda item: item[0]):
            repo, full_name, _group_page_cap, group_estimate = plan[index]
            (
                language,
                readme,
                repo_commits,
                repo_pulls,
                repo_issues,
                group_records,
                group_used,
            ) = future.result()
            records.extend(group_records)
            budget.settle(group_estimate, group_used)
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


def _collect_repo_group(
    client: GitHubClient,
    username: str,
    repo: Repository,
    page_cap: int,
    metrics: CollectionMetrics,
    correlation_id: str,
) -> tuple[
    LanguageStats | None,
    Readme | None,
    list[Commit] | None,
    list[PullRequest] | None,
    list[Issue] | None,
    list[CollectionRecord],
    int,
]:
    """Collect the five metadata resources of one repository.

    Runs the individual collections in the canonical order and returns the
    values, the per-group collection records, and the total requests used by
    the group (so the caller can settle the group's budget reservation).

    The correlation id is set explicitly in this thread so structured log lines
    emitted by worker threads carry the parent run's tag (issue #65).
    """
    with run_correlation(correlation_id):
        full_name = repo.full_name
        if full_name is None or "/" not in full_name:
            return None, None, None, None, None, [], 0
        owner, _, repo_name = full_name.partition("/")
        group_records: list[CollectionRecord] = []
        group_used = 0

        language, used = _run_reserved(
            client,
            group_records,
            f"languages:{full_name}",
            partial(collect_repo_languages, client, owner, repo_name),
            metrics=metrics,
        )
        group_used += used
        readme, used = _run_reserved(
            client,
            group_records,
            f"readme:{full_name}",
            partial(collect_repo_readme, client, owner, repo_name),
            metrics=metrics,
        )
        group_used += used
        repo_commits, used = _run_reserved(
            client,
            group_records,
            f"commits:{full_name}",
            partial(
                collect_commits,
                client,
                owner,
                repo_name,
                author=username,
                max_pages=page_cap,
            ),
            metrics=metrics,
        )
        group_used += used
        repo_pulls, used = _run_reserved(
            client,
            group_records,
            f"pull_requests:{full_name}",
            partial(
                collect_pull_requests,
                client,
                owner,
                repo_name,
                author=username,
                max_pages=page_cap,
            ),
            metrics=metrics,
        )
        group_used += used
        repo_issues, used = _run_reserved(
            client,
            group_records,
            f"issues:{full_name}",
            partial(
                collect_issues,
                client,
                owner,
                repo_name,
                author=username,
                max_pages=page_cap,
            ),
            metrics=metrics,
        )
        group_used += used

        return (
            language,
            readme,
            repo_commits,
            repo_pulls,
            repo_issues,
            group_records,
            group_used,
        )


def _run_reserved(
    client: GitHubClient,
    records: list[CollectionRecord],
    name: str,
    operation: Callable[[], T],
    *,
    metrics: CollectionMetrics,
) -> tuple[T | None, int]:
    """Run one collection whose budget was already reserved by the caller.

    Request usage is measured per thread (via ``thread_requests_made``) so
    concurrent groups never pollute each other's accounting. The budget itself
    is not touched here; the caller settles the group reservation once.
    """
    _logger.debug("collection.start", extra={"collection": name})
    before = client.thread_requests_made
    started = perf_counter()
    try:
        value = operation()
    except Exception as exc:
        used = client.thread_requests_made - before
        duration = perf_counter() - started
        metrics.record_timing(name, duration)
        metrics.increment("errors")
        metrics.increment(f"errors:{name}")
        records.append(
            CollectionRecord(
                name=name,
                status=CollectionStatus.FAILED,
                reason=type(exc).__name__,
                detail=str(exc),
                requests_used=used,
            )
        )
        _logger.warning(
            "collection.failed",
            extra={
                "collection": name,
                "error": type(exc).__name__,
                "detail": str(exc),
                "requests_used": used,
                "duration_seconds": round(duration, 6),
            },
        )
        return None, used
    used = client.thread_requests_made - before
    duration = perf_counter() - started
    metrics.record_timing(name, duration)
    records.append(
        CollectionRecord(
            name=name,
            status=CollectionStatus.SUCCESS,
            requests_used=used,
        )
    )
    _logger.info(
        "collection.end",
        extra={
            "collection": name,
            "requests_used": used,
            "duration_seconds": round(duration, 6),
        },
    )
    return value, used
