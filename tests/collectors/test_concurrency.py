"""Concurrency tests for the collection pipeline (issue #63).

Covers the parallel per-repository metadata phase: snapshot equivalence with
the sequential pipeline, budget-capped burst planning, per-thread request
accounting, and thread safety of the shared client and cache backends.
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from ghdtk.api.cache import CachedResponse, DiskCache, InMemoryCache
from ghdtk.api.client import create_client
from ghdtk.api.rate_limit import BackoffPolicy
from ghdtk.collectors import collect_profile
from ghdtk.models.raw import CollectionStatus

FixtureLoader = Any


def _client(handler: Any, *, cache: Any = None) -> Any:
    return create_client(
        "test-token",
        transport=httpx.MockTransport(handler),
        backoff=BackoffPolicy(
            base_delay=0.0,
            max_delay=0.0,
            sleep_fn=lambda seconds: None,
            random_fn=lambda low, high: 0.0,
        ),
        cache=cache,
    )


def _handler(
    routes: dict[str, Any],
    log: list[str] | None = None,
    *,
    delay: float = 0.0,
) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        if log is not None:
            log.append(request.url.path)
        if delay:
            time.sleep(delay)
        route = routes.get(request.url.path)
        if route is None:
            status, payload = 404, {"message": "Not Found"}
        elif callable(route):
            status, payload = route(request)
        else:
            status, payload = route
        return httpx.Response(status, json=payload, request=request)

    return handler


def _profile_routes(load_raw_fixture: FixtureLoader, count: int) -> dict[str, Any]:
    """Build a mock route table for ``count`` repositories (issue #63)."""
    calendar = {
        "data": {
            "user": {
                "contributionsCollection": {
                    "contributionCalendar": load_raw_fixture("contribution_calendar")
                }
            }
        }
    }

    def search_route(request: httpx.Request) -> tuple[int, Any]:
        query = request.url.params["q"]
        if "type:pr" in query:
            payload = {"total_count": 1, "items": [load_raw_fixture("pull_request_search")]}
        else:
            payload = {"total_count": 1, "items": [load_raw_fixture("issue")]}
        return 200, payload

    routes: dict[str, Any] = {
        "/users/octocat": (200, load_raw_fixture("user")),
        "/users/octocat/followers": (200, [load_raw_fixture("follower")]),
        "/users/octocat/following": (200, [load_raw_fixture("follower")]),
        "/graphql": (200, calendar),
        "/search/issues": search_route,
    }

    repos: list[dict[str, Any]] = []
    for index in range(count):
        repo = {**load_raw_fixture("repository")}
        repo["name"] = f"repo-{index}"
        repo["full_name"] = f"octocat/repo-{index}"
        repo["stargazers_count"] = 1000 - index
        repos.append(repo)
        prefix = f"/repos/octocat/repo-{index}"
        routes[f"{prefix}/languages"] = (200, load_raw_fixture("language_stats"))
        routes[f"{prefix}/readme"] = (200, load_raw_fixture("readme"))
        routes[f"{prefix}/commits"] = (200, [load_raw_fixture("commit")])
        routes[f"{prefix}/pulls"] = (200, [load_raw_fixture("pull_request")])
        routes[f"{prefix}/issues"] = (200, [load_raw_fixture("issue")])

    routes["/users/octocat/repos"] = (200, repos)
    routes["/repos/octocat/repo-0/stargazers"] = (200, [load_raw_fixture("stargazer")])
    return routes


def _cached(key: str) -> CachedResponse:
    now = datetime.now(UTC)
    return CachedResponse(
        key=key,
        url=f"https://api.github.test/{key}",
        status_code=200,
        headers={"ETag": f'"{key}"'},
        content=b"{}",
        stored_at=now,
        expires_at=now + timedelta(seconds=60),
    )


def test_max_workers_validation(load_raw_fixture: FixtureLoader) -> None:
    routes = _profile_routes(load_raw_fixture, 1)
    with _client(_handler(routes)) as client:
        for workers in (0, 33):
            try:
                collect_profile(client, "octocat", max_workers=workers)
            except ValueError:
                continue
            raise AssertionError(f"max_workers={workers} should raise ValueError")


def test_parallel_matches_sequential_multi_repo(load_raw_fixture: FixtureLoader) -> None:
    routes = _profile_routes(load_raw_fixture, 5)
    now = datetime.now(UTC)
    with _client(_handler(routes)) as client:
        sequential = collect_profile(client, "octocat", max_workers=1, now=now)
    with _client(_handler(routes)) as client:
        parallel = collect_profile(client, "octocat", max_workers=4, now=now)

    assert parallel.model_dump_json() == sequential.model_dump_json()
    assert parallel.budget_used == sequential.budget_used
    assert len(parallel.languages) == 5


def test_parallel_large_profile_completes_within_budget(load_raw_fixture: FixtureLoader) -> None:
    routes = _profile_routes(load_raw_fixture, 20)
    with _client(_handler(routes)) as client:
        snapshot = collect_profile(client, "octocat", max_workers=8, max_requests=2000)

    assert len(snapshot.languages) == 20
    assert snapshot.budget_used <= 2000
    assert snapshot.budget_used == 7 + 20 * 5 + 1
    assert snapshot.is_partial is False


def test_parallel_never_exceeds_tight_budget(load_raw_fixture: FixtureLoader) -> None:
    routes = _profile_routes(load_raw_fixture, 5)
    with _client(_handler(routes)) as client:
        snapshot = collect_profile(client, "octocat", max_workers=4, max_requests=40)

    assert snapshot.budget_used <= 40
    skipped = [r for r in snapshot.collections if r.status == CollectionStatus.SKIPPED]
    assert all(r.reason == "budget_exhausted" for r in skipped)
    assert snapshot.is_partial is True


def test_parallel_budget_planning_refuses_overflow_groups(
    load_raw_fixture: FixtureLoader,
) -> None:
    routes = _profile_routes(load_raw_fixture, 5)
    with _client(_handler(routes)) as client:
        snapshot = collect_profile(client, "octocat", max_workers=4, max_requests=40)

    assert snapshot.budget_used == 13
    ran = {r.name for r in snapshot.collections if r.status == CollectionStatus.SUCCESS}
    assert "languages:octocat/repo-0" in ran
    assert "languages:octocat/repo-1" not in ran
    for repo in ("repo-1", "repo-2", "repo-3", "repo-4"):
        skipped = {
            r.name
            for r in snapshot.collections
            if r.status == CollectionStatus.SKIPPED and repo in r.name
        }
        assert skipped == {
            "languages:octocat/" + repo,
            "readme:octocat/" + repo,
            "commits:octocat/" + repo,
            "pull_requests:octocat/" + repo,
            "issues:octocat/" + repo,
        }


def test_parallel_faster_than_sequential_large_profile(
    load_raw_fixture: FixtureLoader,
) -> None:
    routes = _profile_routes(load_raw_fixture, 12)
    now = datetime.now(UTC)
    with _client(_handler(routes, delay=0.01)) as client:
        start = time.perf_counter()
        sequential = collect_profile(client, "octocat", max_workers=1, now=now, max_requests=2000)
        sequential_elapsed = time.perf_counter() - start

    with _client(_handler(routes, delay=0.01)) as client:
        start = time.perf_counter()
        parallel = collect_profile(client, "octocat", max_workers=12, now=now, max_requests=2000)
        parallel_elapsed = time.perf_counter() - start

    assert sequential.budget_used == parallel.budget_used
    assert parallel.model_dump_json() == sequential.model_dump_json()
    assert parallel_elapsed < sequential_elapsed


def test_parallel_per_repo_records_match_sequential(
    load_raw_fixture: FixtureLoader,
) -> None:
    routes = _profile_routes(load_raw_fixture, 3)
    now = datetime.now(UTC)
    with _client(_handler(routes)) as client:
        sequential = collect_profile(client, "octocat", max_workers=1, now=now)
    with _client(_handler(routes)) as client:
        parallel = collect_profile(client, "octocat", max_workers=3, now=now)

    seq_names = [r.name for r in sequential.collections]
    par_names = [r.name for r in parallel.collections]
    assert seq_names == par_names
    assert [r.requests_used for r in parallel.collections] == [
        r.requests_used for r in sequential.collections
    ]


def test_thread_requests_made_accounting() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"login": "octocat"}, request=request)

    with _client(handler) as client:
        for _ in range(5):
            client._request("GET", "/users/octocat")
        assert client.thread_requests_made == 5
        assert client.requests_made == 5

        threads = [
            threading.Thread(
                target=lambda: [client._request("GET", "/users/octocat") for _ in range(3)]
            )
            for _ in range(4)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert client.requests_made == 5 + 12
    assert calls == 17


def test_client_concurrent_requests_no_lost_updates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"login": "octocat"}, request=request)

    with _client(handler) as client:
        errors: list[Exception] = []

        def worker() -> None:
            try:
                for _ in range(10):
                    client._request("GET", "/users/octocat")
            except Exception as exc:  # pragma: no cover - unexpected
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not errors
        assert client.requests_made == 80


def test_in_memory_cache_concurrent_access() -> None:
    cache = InMemoryCache()

    def worker(thread_id: int) -> None:
        for i in range(50):
            key = f"k-{thread_id}-{i}"
            cache.set(key, _cached(key))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(cache) == 8 * 50
    assert cache.get("k-3-49") is not None
    assert cache.get("missing") is None


def test_disk_cache_concurrent_access(tmp_path: Any) -> None:
    cache = DiskCache(tmp_path)

    def worker(thread_id: int) -> None:
        for i in range(50):
            key = f"d-{thread_id}-{i}"
            cache.set(key, _cached(key))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert cache.get("d-5-49") is not None
    assert cache.get("missing") is None
    cache.clear()
    assert cache.get("d-5-49") is None
