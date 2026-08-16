"""Tests for the recorded-response corpus and replay transport (issue #59).

The corpus is the versioned, documented fixture set that both unit tests and
the end-to-end replay runner build on. These tests pin the format: sessions
must be versioned, coherent and complete enough that a full collection never
needs a request outside the session (i.e. never hits the live API).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest
from replay import (
    CORPUS_DIR,
    CORPUS_VERSION,
    ReplayTransport,
    SessionVersionError,
    UnrecordedRequestError,
    client_from_session,
    list_profiles,
    load_session,
)

from ghdtk.api.errors import MalformedResponseError, RateLimitError, UserNotFoundError
from ghdtk.collectors.orchestrator import collect_profile
from ghdtk.models.raw import CollectionStatus, ProfileSnapshot

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _session_repo_full_names(session: dict[str, Any]) -> set[str]:
    repos = _entry_for(session, "GET", "/users/{username}/repos")["response"]["body"]
    return {repo["full_name"] for repo in repos}


def _entry_for(
    session: dict[str, Any],
    method: str,
    path: str,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    path = path.format(username=session["profile"]["username"])
    candidates = [
        entry
        for entry in session["requests"]
        if entry["method"] == method and entry["path"] == path
    ]
    if params is None:
        if not candidates:
            raise AssertionError(f"No entry for {method} {path}")
        return cast(dict[str, Any], candidates[0])
    for entry in candidates:
        if entry.get("params", {}) == params:
            return cast(dict[str, Any], entry)
    raise AssertionError(f"No entry for {method} {path} {params}")


def test_manifest_is_versioned_and_indexes_profiles() -> None:
    manifest = json.loads((CORPUS_DIR / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["version"] == CORPUS_VERSION
    ids = [entry["id"] for entry in manifest["profiles"]]
    assert set(ids) == {
        "active-developer",
        "minimal-profile",
        "newcomer",
        "popular-maintainer",
        "archived-heavy",
        "hidden-activity",
        "errors/user-not-found",
        "errors/rate-limit",
        "errors/malformed",
    }


def test_every_indexed_session_exists_and_matches_manifest() -> None:
    manifest = json.loads((CORPUS_DIR / "MANIFEST.json").read_text(encoding="utf-8"))
    for entry in manifest["profiles"]:
        session = load_session(entry["id"])
        assert session["version"] == CORPUS_VERSION
        assert session["profile"]["id"] == entry["id"].split("/", 1)[-1]
        assert len(session["requests"]) == entry["requests"]
        assert len(session["requests"]) > 0


def test_every_session_has_metadata() -> None:
    for profile_id in [
        *list_profiles(),
        "errors/user-not-found",
        "errors/rate-limit",
        "errors/malformed",
    ]:
        session = load_session(profile_id)
        profile = session["profile"]
        assert profile["username"]
        assert profile["description"]
        assert profile["now"] == "2026-01-01T12:00:00Z"


@pytest.mark.parametrize("profile_id", list_profiles())
def test_full_collection_uses_only_recorded_requests(profile_id: str) -> None:
    """Strict replay means any unknown request raises: no live API, no gaps."""
    session = load_session(profile_id)
    client = client_from_session(session)
    collect_profile(client, session["profile"]["username"], now=NOW)
    assert client.requests_made == len(session["requests"])


@pytest.mark.parametrize("profile_id", list_profiles())
def test_full_collection_succeeds_for_every_profile(profile_id: str) -> None:
    session = load_session(profile_id)
    client = client_from_session(session)
    snapshot = collect_profile(client, session["profile"]["username"], now=NOW)
    for record in snapshot.collections:
        assert record.status != CollectionStatus.FAILED, record
    assert snapshot.user is not None
    assert snapshot.contribution_calendar is not None
    assert snapshot.budget_used > 0


@pytest.mark.parametrize("profile_id", list_profiles())
def test_collection_is_deterministic(profile_id: str) -> None:
    session = load_session(profile_id)
    username = session["profile"]["username"]
    first = collect_profile(client_from_session(session), username, now=NOW)
    second = collect_profile(client_from_session(session), username, now=NOW)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_search_items_reference_known_repositories() -> None:
    for profile_id in list_profiles():
        session = load_session(profile_id)
        username = session["profile"]["username"]
        full_names = _session_repo_full_names(session)
        for query in (f"author:{username} type:pr", f"author:{username} type:issue"):
            entry = _entry_for(
                session,
                "GET",
                "/search/issues",
                {"q": query, "per_page": "100", "page": "1"},
            )
            for item in entry["response"]["body"]["items"]:
                repo_url = item["repository_url"]
                full_name = repo_url.removeprefix("https://api.github.com/repos/")
                assert full_name in full_names, f"{profile_id}: {query} references {full_name}"


def test_every_repository_has_endpoint_entries() -> None:
    for profile_id in list_profiles():
        session = load_session(profile_id)
        full_names = _session_repo_full_names(session)
        for full_name in full_names:
            owner, _, repo = full_name.partition("/")
            for suffix in ("languages", "readme", "commits", "pulls", "issues"):
                _entry_for(session, "GET", f"/repos/{owner}/{repo}/{suffix}")


@pytest.mark.parametrize("profile_id", list_profiles())
def test_stargazers_target_top_non_fork_repository(profile_id: str) -> None:
    session = load_session(profile_id)
    stargazer_entries = [e for e in session["requests"] if e["path"].endswith("/stargazers")]
    if profile_id == "minimal-profile":
        assert stargazer_entries == []
        return
    assert stargazer_entries
    repos = _entry_for(session, "GET", "/users/{username}/repos")["response"]["body"]
    top = max(
        (repo for repo in repos if not repo["fork"]), key=lambda repo: repo["stargazers_count"]
    )
    stargazer_path = f"/repos/{top['full_name']}/stargazers"
    assert all(e["path"] == stargazer_path for e in stargazer_entries)


def test_replay_transport_rejects_unknown_versions() -> None:
    with pytest.raises(SessionVersionError):
        ReplayTransport({"version": 99, "requests": []})


def test_replay_transport_raises_on_unrecorded_request_in_strict_mode() -> None:
    session = load_session("minimal-profile")
    transport = ReplayTransport(session)
    request = httpx.Request("GET", "https://api.github.com/users/unknown")
    with pytest.raises(UnrecordedRequestError):
        transport.handle_request(request)


def test_replay_transport_is_lenient_outside_strict_mode() -> None:
    session = load_session("minimal-profile")
    transport = ReplayTransport(session, strict=False)
    request = httpx.Request("GET", "https://api.github.com/users/unknown")
    response = transport.handle_request(request)
    assert response.status_code == 404


def test_replay_transport_returns_recorded_body_and_headers() -> None:
    session = load_session("minimal-profile")
    transport = ReplayTransport(session)
    username = session["profile"]["username"]
    request = httpx.Request("GET", f"https://api.github.com/users/{username}")
    response = transport.handle_request(request)
    assert response.status_code == 200
    assert response.json()["login"] == username


def test_replay_transport_rejects_duplicate_entries() -> None:
    entry = {"method": "GET", "path": "/users/dup", "response": {"status": 200, "body": {}}}
    with pytest.raises(ValueError, match="Duplicate"):
        ReplayTransport({"version": CORPUS_VERSION, "requests": [entry, entry]})


def test_malformed_session_missing_requests_is_rejected() -> None:
    with pytest.raises(ValueError, match="requests"):
        ReplayTransport({"version": CORPUS_VERSION, "requests": "nope"})


@pytest.mark.parametrize(
    ("profile_id", "error_type"),
    [
        ("errors/user-not-found", UserNotFoundError),
        ("errors/rate-limit", RateLimitError),
        ("errors/malformed", MalformedResponseError),
    ],
)
def test_error_sessions_raise_typed_errors(profile_id: str, error_type: type[Exception]) -> None:
    session = load_session(profile_id)
    client = client_from_session(session)
    with pytest.raises(error_type):
        client.get_user(session["profile"]["username"])


@pytest.mark.parametrize("profile_id", list_profiles())
def test_snapshot_round_trips_through_json(profile_id: str) -> None:
    session = load_session(profile_id)
    snapshot = collect_profile(
        client_from_session(session), session["profile"]["username"], now=NOW
    )
    restored = ProfileSnapshot.model_validate(snapshot.model_dump(mode="json"))
    assert restored == snapshot
