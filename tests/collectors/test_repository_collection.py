"""Unit tests for repository data collection (issue #28).

The #22 pipeline already fetches the full repository list with pagination and
per-repo languages; these tests pin the acceptance criteria: paginated
collection across many repositories, topics captured, and fork/archived flags
preserved on the raw snapshot.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

from ghdtk.api.client import create_client
from ghdtk.api.rate_limit import BackoffPolicy
from ghdtk.collectors import collect_profile
from ghdtk.models.raw import CollectionStatus

FixtureLoader = Any


def _client(handler: Any) -> Any:
    return create_client(
        "test-token",
        transport=httpx.MockTransport(handler),
        backoff=BackoffPolicy(
            base_delay=0.0,
            max_delay=0.0,
            sleep_fn=lambda seconds: None,
            random_fn=lambda low, high: 0.0,
        ),
    )


def _handler(routes: dict[str, tuple[int, Any]]) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        status, payload = routes.get(request.url.path, (404, {"message": "Not Found"}))
        return httpx.Response(status, json=payload, request=request)

    return handler


def _repos_handler(
    pages: list[list[dict[str, Any]]],
    log: list[str] | None = None,
) -> Callable[[httpx.Request], httpx.Response]:
    """Page-aware handler that follows Link-header pagination."""

    def handler(request: httpx.Request) -> httpx.Response:
        if log is not None:
            log.append(str(request.url))
        page = int(request.url.params.get("page", 1))
        if page > len(pages):
            return httpx.Response(200, json=[], request=request)
        link = (
            f'<https://api.github.com/users/octocat/repos?page={page + 1}>; rel="next"'
            if page < len(pages)
            else None
        )
        headers = {"Link": link} if link else {}
        return httpx.Response(200, json=pages[page - 1], headers=headers, request=request)

    return handler


def _routes(
    load_raw_fixture: FixtureLoader,
    repo_names: list[tuple[str, str]],
) -> dict[str, tuple[int, Any]]:
    """Standard routes for user/calendar/followers and per-repo endpoints."""
    calendar = {
        "data": {
            "user": {
                "contributionsCollection": {
                    "contributionCalendar": load_raw_fixture("contribution_calendar")
                }
            }
        }
    }
    routes: dict[str, tuple[int, Any]] = {
        "/users/octocat": (200, load_raw_fixture("user")),
        "/graphql": (200, calendar),
        "/users/octocat/followers": (200, [load_raw_fixture("follower")]),
    }
    for owner, repo in repo_names:
        routes[f"/repos/{owner}/{repo}/languages"] = (200, load_raw_fixture("language_stats"))
        routes[f"/repos/{owner}/{repo}/readme"] = (200, load_raw_fixture("readme"))
        routes[f"/repos/{owner}/{repo}/commits"] = (200, [load_raw_fixture("commit")])
        routes[f"/repos/{owner}/{repo}/pulls"] = (200, [load_raw_fixture("pull_request")])
        routes[f"/repos/{owner}/{repo}/issues"] = (200, [load_raw_fixture("issue")])
    routes["/repos/octocat/Hello-World/stargazers"] = (200, [load_raw_fixture("stargazer")])
    return routes


def test_collect_profile_paginates_many_repositories(
    load_raw_fixture: FixtureLoader,
) -> None:
    page_one = [load_raw_fixture("repository"), load_raw_fixture("repository_forked")]
    page_two = [load_raw_fixture("repository_archived")]
    log: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/users/octocat/repos":
            return _repos_handler([page_one, page_two], log=log)(request)
        return _handler(_routes(load_raw_fixture, [("octocat", "Hello-World")]))(request)

    with _client(handler) as client:
        snapshot = collect_profile(client, "octocat")

    assert snapshot.repositories is not None
    assert [repo.full_name for repo in snapshot.repositories] == [
        "octocat/Hello-World",
        "octocat/Forked",
        "octocat/Archived",
    ]
    assert any("page=2" in entry for entry in log)
    repos_record = next(record for record in snapshot.collections if record.name == "repositories")
    assert repos_record.status == CollectionStatus.SUCCESS
    assert repos_record.requests_used == 2


def test_topics_captured(load_raw_fixture: FixtureLoader) -> None:
    repo_list = [load_raw_fixture("repository_archived")]
    handler = _repos_handler([repo_list])

    def route(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/users/octocat/repos":
            return handler(request)
        return _handler(_routes(load_raw_fixture, [("octocat", "Archived")]))(request)

    with _client(route) as client:
        snapshot = collect_profile(client, "octocat")

    archived = next(
        repo for repo in snapshot.repositories or [] if repo.full_name == "octocat/Archived"
    )
    assert archived.topics == ["archive", "legacy"]


def test_fork_and_archived_flags_preserved(load_raw_fixture: FixtureLoader) -> None:
    repo_list = [
        load_raw_fixture("repository_forked"),
        load_raw_fixture("repository_archived"),
    ]

    def route(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/users/octocat/repos":
            return _repos_handler([repo_list])(request)
        return _handler(
            _routes(load_raw_fixture, [("octocat", "Forked"), ("octocat", "Archived")])
        )(request)

    with _client(route) as client:
        snapshot = collect_profile(client, "octocat")

    repos = {repo.full_name: repo for repo in snapshot.repositories or []}
    assert repos["octocat/Forked"].fork is True
    assert repos["octocat/Forked"].archived is False
    assert repos["octocat/Archived"].archived is True
    assert repos["octocat/Archived"].fork is False


def test_per_repo_languages_collected_for_all_repos(
    load_raw_fixture: FixtureLoader,
) -> None:
    repo_list = [load_raw_fixture("repository_forked"), load_raw_fixture("repository_archived")]
    all_repos = [("octocat", "Forked"), ("octocat", "Archived")]

    def route(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/users/octocat/repos":
            return _repos_handler([repo_list])(request)
        return _handler(_routes(load_raw_fixture, all_repos))(request)

    with _client(route) as client:
        snapshot = collect_profile(client, "octocat")

    assert set(snapshot.languages) == {"octocat/Forked", "octocat/Archived"}
    for stats in snapshot.languages.values():
        assert stats.total_bytes > 0
