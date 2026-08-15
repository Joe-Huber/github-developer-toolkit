"""Unit tests for the API response caching layer (issue #21)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from ghdtk.api.cache import (
    CachedResponse,
    DiskCache,
    InMemoryCache,
    ResponseCache,
    cache_key,
    default_cache_directory,
)
from ghdtk.api.client import create_client

FixtureLoader = Any

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _entry(key: str, **overrides: Any) -> CachedResponse:
    defaults: dict[str, Any] = {
        "key": key,
        "url": "https://api.github.com/x",
        "status_code": 200,
        "headers": {"Content-Type": "application/json"},
        "content": b"{}",
        "stored_at": NOW,
        "expires_at": NOW + timedelta(hours=1),
        "etag": None,
    }
    defaults.update(overrides)
    return CachedResponse(**defaults)


# --- cache_key ----------------------------------------------------------------


def test_cache_key_is_deterministic_hash() -> None:
    url = "https://api.github.com/users/octocat"
    assert cache_key("GET", url) == cache_key("get", url)
    assert len(cache_key("GET", url)) == 64
    assert cache_key("GET", url) != cache_key("GET", "https://api.github.com/users/torvalds")


def test_default_cache_directory_is_safe() -> None:
    directory = default_cache_directory()
    assert str(directory).endswith((".cache/ghdtk", "ghdtk"))


# --- InMemoryCache ---------------------------------------------------------------


def test_in_memory_cache_lifecycle() -> None:
    cache = InMemoryCache()
    entry = _entry("k")
    assert cache.get("k") is None
    cache.set("k", entry)
    assert cache.get("k") is entry
    cache.delete("k")
    assert cache.get("k") is None
    cache.set("k", entry)
    cache.set("k2", entry)
    cache.clear()
    assert len(cache) == 0


# --- DiskCache --------------------------------------------------------------------


def test_disk_cache_round_trip_redacts_url(tmp_path: Any) -> None:
    cache = DiskCache(tmp_path)
    cache.set("k", _entry("k", etag="abc"))
    loaded = cache.get("k")
    assert loaded is not None
    assert loaded.content == b"{}"
    assert loaded.etag == "abc"
    assert loaded.url == "<redacted>"


def test_disk_cache_round_trip_preserves_dates(tmp_path: Any) -> None:
    cache = DiskCache(tmp_path)
    cache.set("k", _entry("k"))
    loaded = cache.get("k")
    assert loaded is not None
    assert loaded.stored_at == NOW
    assert loaded.expires_at == NOW + timedelta(hours=1)


def test_disk_cache_corrupt_file_is_miss(tmp_path: Any) -> None:
    cache = DiskCache(tmp_path)
    (tmp_path / "deadbeef.json").write_text("not json", encoding="utf-8")
    assert cache.get("deadbeef") is None


def test_disk_cache_delete_and_clear(tmp_path: Any) -> None:
    cache = DiskCache(tmp_path)
    cache.set("a", _entry("a"))
    cache.set("b", _entry("b"))
    cache.delete("a")
    assert cache.get("a") is None
    assert cache.get("b") is not None
    cache.clear()
    assert cache.get("b") is None


# --- ResponseCache -----------------------------------------------------------------


def test_response_cache_freshness() -> None:
    cache = ResponseCache(InMemoryCache(), ttl_seconds=3600)
    entry = _entry("k")
    assert cache.is_fresh(entry, now=NOW + timedelta(minutes=30))
    assert not cache.is_fresh(entry, now=NOW + timedelta(hours=2))


def test_response_cache_set_from_response() -> None:
    cache = ResponseCache(InMemoryCache(), ttl_seconds=3600)
    request = httpx.Request("GET", "https://api.github.com/users/octocat")
    response = httpx.Response(
        200,
        json={"login": "octocat"},
        headers={"ETag": "abc"},
        request=request,
    )
    cache.set("k", response, "https://api.github.com/users/octocat")
    entry = cache.get("k")
    assert entry is not None
    assert entry.etag == "abc"
    assert cache.is_fresh(entry)
    assert entry.content == response.content


def test_response_cache_revalidate() -> None:
    cache = ResponseCache(InMemoryCache(), ttl_seconds=3600)
    stale = _entry(
        "k",
        stored_at=NOW - timedelta(hours=2),
        expires_at=NOW - timedelta(hours=1),
    )
    cache.backend.set("k", stale)
    refreshed = cache.revalidate("k", stale)
    entry = cache.get("k")
    assert entry is not None
    assert cache.is_fresh(entry)
    assert refreshed.content == stale.content


# --- client integration --------------------------------------------------------------


def test_client_serves_fresh_cache_hit(load_raw_fixture: FixtureLoader) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=load_raw_fixture("user"), request=request)

    cache = ResponseCache(InMemoryCache(), ttl_seconds=3600)
    with create_client("token", transport=httpx.MockTransport(handler), cache=cache) as client:
        first = client.get_user("octocat")
        second = client.get_user("octocat")
    assert first.login == second.login == "octocat"
    assert len(calls) == 1
    assert client.requests_made == 1


def test_client_revalidates_stale_entry_with_etag(load_raw_fixture: FixtureLoader) -> None:
    payload = load_raw_fixture("user")
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("If-None-Match"))
        return httpx.Response(304, headers={"ETag": '"abc"'}, request=request)

    cache = ResponseCache(InMemoryCache(), ttl_seconds=3600)
    key = cache_key("GET", "https://api.github.com/users/octocat")
    cache.backend.set(
        key,
        _entry(
            key,
            url="https://api.github.com/users/octocat",
            content=json.dumps(payload).encode(),
            stored_at=NOW - timedelta(hours=2),
            expires_at=NOW - timedelta(hours=1),
            etag='"abc"',
        ),
    )
    with create_client("token", transport=httpx.MockTransport(handler), cache=cache) as client:
        user = client.get_user("octocat")
    assert user.login == "octocat"
    assert seen == ['"abc"']
    entry = cache.get(key)
    assert entry is not None
    assert cache.is_fresh(entry)


def test_client_refetches_when_stale_etag_changed(load_raw_fixture: FixtureLoader) -> None:
    payload = load_raw_fixture("user")
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=payload, request=request)

    cache = ResponseCache(InMemoryCache(), ttl_seconds=3600)
    key = cache_key("GET", "https://api.github.com/users/octocat")
    cache.backend.set(
        key,
        _entry(
            key,
            url="https://api.github.com/users/octocat",
            content=b"{}",
            stored_at=NOW - timedelta(hours=2),
            expires_at=NOW - timedelta(hours=1),
            etag='"old"',
        ),
    )
    with create_client("token", transport=httpx.MockTransport(handler), cache=cache) as client:
        user = client.get_user("octocat")
    assert user.login == "octocat"
    assert len(calls) == 1
    entry = cache.get(key)
    assert entry is not None
    assert entry.etag is None


def test_client_ignores_cache_when_disabled(load_raw_fixture: FixtureLoader) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=load_raw_fixture("user"), request=request)

    with create_client("token", transport=httpx.MockTransport(handler)) as client:
        client.get_user("octocat")
        client.get_user("octocat")
    assert len(calls) == 2
