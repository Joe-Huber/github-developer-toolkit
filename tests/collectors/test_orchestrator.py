"""Unit tests for the profile collection orchestrator (issue #22).

Exercises the full pipeline against a mocked transport: budget enforcement,
partial-success aggregation, continue-on-failure, and the stargazer target
selection.
"""

from __future__ import annotations

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


def _routes(load_raw_fixture: FixtureLoader) -> dict[str, tuple[int, Any]]:
    calendar = {
        "data": {
            "user": {
                "contributionsCollection": {
                    "contributionCalendar": load_raw_fixture("contribution_calendar")
                }
            }
        }
    }
    return {
        "/users/octocat": (200, load_raw_fixture("user")),
        "/users/octocat/repos": (200, [load_raw_fixture("repository")]),
        "/graphql": (200, calendar),
        "/users/octocat/followers": (200, [load_raw_fixture("follower")]),
        "/repos/octocat/Hello-World/languages": (200, load_raw_fixture("language_stats")),
        "/repos/octocat/Hello-World/readme": (200, load_raw_fixture("readme")),
        "/repos/octocat/Hello-World/commits": (200, [load_raw_fixture("commit")]),
        "/repos/octocat/Hello-World/pulls": (200, [load_raw_fixture("pull_request")]),
        "/repos/octocat/Hello-World/issues": (200, [load_raw_fixture("issue")]),
        "/repos/octocat/Hello-World/stargazers": (200, [load_raw_fixture("stargazer")]),
    }


def _handler(routes: dict[str, tuple[int, Any]], log: list[str] | None = None) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        if log is not None:
            log.append(request.url.path)
        status, payload = routes.get(request.url.path, (404, {"message": "Not Found"}))
        return httpx.Response(status, json=payload, request=request)

    return handler


def test_collect_profile_full_run(load_raw_fixture: FixtureLoader) -> None:
    routes = _routes(load_raw_fixture)
    with _client(_handler(routes)) as client:
        snapshot = collect_profile(client, "octocat")

    assert snapshot.username == "octocat"
    assert snapshot.user is not None and snapshot.user.login == "octocat"
    assert snapshot.repositories is not None
    assert [repo.full_name for repo in snapshot.repositories] == ["octocat/Hello-World"]
    assert snapshot.languages["octocat/Hello-World"] is not None
    assert snapshot.readmes["octocat/Hello-World"] is not None
    assert snapshot.commits["octocat/Hello-World"]
    assert snapshot.pull_requests["octocat/Hello-World"]
    assert snapshot.issues["octocat/Hello-World"]
    assert snapshot.followers is not None and len(snapshot.followers) == 1
    assert snapshot.stargazers is not None and len(snapshot.stargazers) == 1
    assert snapshot.contribution_calendar is not None
    assert snapshot.budget_max == 500
    assert snapshot.budget_used == 10
    assert len(snapshot.collections) == 10
    assert all(record.status == CollectionStatus.SUCCESS for record in snapshot.collections)
    assert snapshot.is_partial is False


def test_collect_profile_respects_max_requests(load_raw_fixture: FixtureLoader) -> None:
    routes = _routes(load_raw_fixture)
    with _client(_handler(routes)) as client:
        snapshot = collect_profile(client, "octocat", max_requests=25)
    assert snapshot.budget_max == 25
    assert snapshot.budget_used == 10


def test_collect_profile_stops_when_budget_exhausted(load_raw_fixture: FixtureLoader) -> None:
    routes = _routes(load_raw_fixture)
    with _client(_handler(routes)) as client:
        snapshot = collect_profile(client, "octocat", max_requests=2)

    assert snapshot.user is not None
    assert snapshot.repositories is not None
    assert snapshot.contribution_calendar is None
    assert snapshot.followers is None
    assert snapshot.languages == {}
    assert snapshot.stargazers is None
    assert snapshot.budget_used == 2
    skipped = [r for r in snapshot.collections if r.status == CollectionStatus.SKIPPED]
    assert len(skipped) == len(snapshot.collections) - 2
    assert all(r.reason == "budget_exhausted" for r in skipped)
    assert snapshot.is_partial is True


def test_collect_profile_continues_on_failure(load_raw_fixture: FixtureLoader) -> None:
    routes = _routes(load_raw_fixture)
    routes["/repos/octocat/Hello-World/readme"] = (500, {"message": "boom"})
    with _client(_handler(routes)) as client:
        snapshot = collect_profile(client, "octocat")

    assert snapshot.readmes == {}
    assert snapshot.languages["octocat/Hello-World"] is not None
    failed = [r for r in snapshot.collections if r.status == CollectionStatus.FAILED]
    assert len(failed) == 1
    assert failed[0].name == "readme:octocat/Hello-World"
    assert failed[0].reason == "GitHubAPIError"
    assert snapshot.is_partial is True


def test_collect_profile_without_repositories(load_raw_fixture: FixtureLoader) -> None:
    routes = _routes(load_raw_fixture)
    routes["/users/octocat/repos"] = (200, [])
    with _client(_handler(routes)) as client:
        snapshot = collect_profile(client, "octocat")

    assert snapshot.repositories == []
    assert snapshot.languages == {}
    stargazers = next(r for r in snapshot.collections if r.name == "stargazers")
    assert stargazers.status == CollectionStatus.SKIPPED
    assert stargazers.reason == "no_repositories"
    assert snapshot.is_partial is True


def test_collect_profile_user_not_found_is_partial(load_raw_fixture: FixtureLoader) -> None:
    routes = _routes(load_raw_fixture)
    routes["/users/octocat"] = (404, {"message": "Not Found"})
    routes["/users/octocat/repos"] = (404, {"message": "Not Found"})
    routes["/users/octocat/followers"] = (404, {"message": "Not Found"})
    routes["/graphql"] = (200, {"data": {"user": None}})
    with _client(_handler(routes)) as client:
        snapshot = collect_profile(client, "octocat")

    assert snapshot.user is None
    assert snapshot.repositories is None
    assert snapshot.contribution_calendar is None
    failed = {r.name: r for r in snapshot.collections if r.status == CollectionStatus.FAILED}
    assert failed["user"].reason == "UserNotFoundError"
    assert failed["repositories"].reason == "UserNotFoundError"
    assert failed["contribution_calendar"].reason == "UserNotFoundError"
    assert failed["followers"].reason == "UserNotFoundError"
    assert snapshot.is_partial is True


def test_stargazers_target_most_starred_repository(load_raw_fixture: FixtureLoader) -> None:
    routes = _routes(load_raw_fixture)
    starred = {
        **load_raw_fixture("repository"),
        "full_name": "octocat/Starred",
        "name": "Starred",
        "stargazers_count": 200,
    }
    routes["/users/octocat/repos"] = (200, [load_raw_fixture("repository"), starred])
    routes["/repos/octocat/Starred/languages"] = (200, load_raw_fixture("language_stats"))
    routes["/repos/octocat/Starred/readme"] = (200, load_raw_fixture("readme"))
    routes["/repos/octocat/Starred/commits"] = (200, [load_raw_fixture("commit")])
    routes["/repos/octocat/Starred/pulls"] = (200, [load_raw_fixture("pull_request")])
    routes["/repos/octocat/Starred/issues"] = (200, [load_raw_fixture("issue")])
    routes["/repos/octocat/Starred/stargazers"] = (200, [load_raw_fixture("stargazer")])

    log: list[str] = []
    with _client(_handler(routes, log=log)) as client:
        snapshot = collect_profile(client, "octocat")

    assert snapshot.languages["octocat/Starred"] is not None
    assert snapshot.languages["octocat/Hello-World"] is not None
    assert snapshot.stargazers is not None
    assert "/repos/octocat/Starred/stargazers" in log


def test_stargazers_skip_forks_and_record_names_repository(
    load_raw_fixture: FixtureLoader,
) -> None:
    routes = _routes(load_raw_fixture)
    forked = {
        **load_raw_fixture("repository"),
        "full_name": "octocat/Forked",
        "name": "Forked",
        "stargazers_count": 500,
        "fork": True,
    }
    routes["/users/octocat/repos"] = (200, [load_raw_fixture("repository"), forked])
    routes["/repos/octocat/Forked/languages"] = (200, load_raw_fixture("language_stats"))
    routes["/repos/octocat/Forked/readme"] = (200, load_raw_fixture("readme"))
    routes["/repos/octocat/Forked/commits"] = (200, [load_raw_fixture("commit")])
    routes["/repos/octocat/Forked/pulls"] = (200, [load_raw_fixture("pull_request")])
    routes["/repos/octocat/Forked/issues"] = (200, [load_raw_fixture("issue")])

    log: list[str] = []
    with _client(_handler(routes, log=log)) as client:
        snapshot = collect_profile(client, "octocat")

    assert "/repos/octocat/Forked/stargazers" not in log
    assert "/repos/octocat/Hello-World/stargazers" in log
    record = next(r for r in snapshot.collections if r.name.startswith("stargazers:"))
    assert record.name == "stargazers:octocat/Hello-World"
    assert record.status == CollectionStatus.SUCCESS
    assert snapshot.is_partial is False
