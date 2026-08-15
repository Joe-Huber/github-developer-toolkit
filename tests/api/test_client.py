"""Unit tests for the typed GitHub API client (issue #17).

Exercises every typed endpoint with a mocked transport, verifies the client is
injectable (no global state), and checks that auth/not-found/rate-limit and
malformed/validation failures surface as typed errors.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from ghdtk.api.client import (
    STARGAZER_TIMELINE_ACCEPT,
    GitHubClient,
    create_client,
)
from ghdtk.api.errors import (
    APITimeoutError,
    AuthenticationError,
    DataValidationError,
    MalformedResponseError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    UserNotFoundError,
)

FixtureLoader = Any


def _client(handler: Any) -> GitHubClient:
    return create_client("test-token", transport=httpx.MockTransport(handler))


def _json_response(request: httpx.Request, payload: Any, *, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload, request=request)


def test_get_user(load_raw_fixture: FixtureLoader) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/users/octocat"
        assert request.headers["Authorization"] == "Bearer test-token"
        return _json_response(request, load_raw_fixture("user"))

    with _client(handler) as client:
        user = client.get_user("octocat")
    assert user.login == "octocat"
    assert user.followers == 20


def test_get_authenticated_user(load_raw_fixture: FixtureLoader) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/user"
        return _json_response(request, load_raw_fixture("user"))

    with _client(handler) as client:
        user = client.get_authenticated_user()
    assert user.login == "octocat"


def test_list_user_repositories(load_raw_fixture: FixtureLoader) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/users/octocat/repos"
        assert request.url.params["per_page"] == "100"
        assert request.url.params["page"] == "1"
        return _json_response(request, [load_raw_fixture("repository")])

    with _client(handler) as client:
        repos = client.list_user_repositories("octocat")
    assert len(repos) == 1
    assert repos[0].full_name == "octocat/Hello-World"


def test_get_repository(load_raw_fixture: FixtureLoader) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/octocat/Hello-World"
        return _json_response(request, load_raw_fixture("repository"))

    with _client(handler) as client:
        repo = client.get_repository("octocat", "Hello-World")
    assert repo.full_name == "octocat/Hello-World"
    assert repo.stargazers_count == 80


def test_get_languages(load_raw_fixture: FixtureLoader) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/octocat/Hello-World/languages"
        return _json_response(request, load_raw_fixture("language_stats"))

    with _client(handler) as client:
        stats = client.get_languages("octocat", "Hello-World")
    assert stats.root["Python"] == 38739
    assert stats.total_bytes == 82_249


def test_get_readme(load_raw_fixture: FixtureLoader) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/octocat/Hello-World/readme"
        return _json_response(request, load_raw_fixture("readme"))

    with _client(handler) as client:
        readme = client.get_readme("octocat", "Hello-World")
    assert readme is not None
    assert readme.decoded_content is not None
    assert "# Acme Toolkit" in readme.decoded_content


def test_get_readme_missing_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(request, {"message": "Not Found"}, status=404)

    with _client(handler) as client:
        assert client.get_readme("octocat", "no-readme") is None


def test_list_commits_with_author(load_raw_fixture: FixtureLoader) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/octocat/Hello-World/commits"
        assert request.url.params["author"] == "octocat"
        return _json_response(request, [load_raw_fixture("commit")])

    with _client(handler) as client:
        commits = client.list_commits("octocat", "Hello-World", author="octocat")
    assert len(commits) == 1
    assert commits[0].sha is not None
    assert commits[0].sha.startswith("c441029")


def test_list_pull_requests(load_raw_fixture: FixtureLoader) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/octocat/Hello-World/pulls"
        assert request.url.params["state"] == "open"
        return _json_response(request, [load_raw_fixture("pull_request")])

    with _client(handler) as client:
        pulls = client.list_pull_requests("octocat", "Hello-World", state="open")
    assert len(pulls) == 1
    assert pulls[0].number == 1347


def test_list_issues(load_raw_fixture: FixtureLoader) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/octocat/Hello-World/issues"
        return _json_response(request, [load_raw_fixture("issue")])

    with _client(handler) as client:
        issues = client.list_issues("octocat", "Hello-World")
    assert len(issues) == 1
    assert issues[0].title == "Found a bug"


def test_list_followers(load_raw_fixture: FixtureLoader) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/users/octocat/followers"
        return _json_response(request, [load_raw_fixture("follower")])

    with _client(handler) as client:
        followers = client.list_followers("octocat")
    assert len(followers) == 1
    assert followers[0].login == "torvalds"


def test_list_stargazers_uses_timeline_header(load_raw_fixture: FixtureLoader) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/octocat/Hello-World/stargazers"
        assert request.headers["Accept"] == STARGAZER_TIMELINE_ACCEPT
        return _json_response(request, [load_raw_fixture("stargazer")])

    with _client(handler) as client:
        stargazers = client.list_stargazers("octocat", "Hello-World")
    assert len(stargazers) == 1
    assert stargazers[0].login == "octocat"


def test_search_commits(load_raw_fixture: FixtureLoader) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search/commits"
        assert request.url.params["q"] == "author:octocat"
        return _json_response(request, {"total_count": 1, "items": [load_raw_fixture("commit")]})

    with _client(handler) as client:
        commits = client.search_commits("author:octocat")
    assert len(commits) == 1


def test_search_pull_requests(load_raw_fixture: FixtureLoader) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search/issues"
        assert "is:pr" in request.url.params["q"]
        return _json_response(
            request, {"total_count": 1, "items": [load_raw_fixture("pull_request")]}
        )

    with _client(handler) as client:
        pulls = client.search_pull_requests("author:octocat is:pr")
    assert len(pulls) == 1
    assert pulls[0].number == 1347


def test_search_issues(load_raw_fixture: FixtureLoader) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search/issues"
        return _json_response(request, {"total_count": 1, "items": [load_raw_fixture("issue")]})

    with _client(handler) as client:
        issues = client.search_issues("author:octocat")
    assert len(issues) == 1


def test_contribution_calendar(load_raw_fixture: FixtureLoader) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/graphql"
        assert request.method == "POST"
        body = request.read().decode()
        assert '"login"' in body and "octocat" in body
        calendar = load_raw_fixture("contribution_calendar")
        return _json_response(
            request,
            {"data": {"user": {"contributionsCollection": {"contributionCalendar": calendar}}}},
        )

    with _client(handler) as client:
        calendar = client.get_contribution_calendar("octocat")
    assert calendar.total_contributions == 100


def test_contribution_calendar_user_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(request, {"data": {"user": None}})

    with _client(handler) as client:
        with pytest.raises(UserNotFoundError):
            client.get_contribution_calendar("ghost")


def test_auth_failure_is_typed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(request, {"message": "Bad credentials"}, status=401)

    with _client(handler) as client:
        with pytest.raises(AuthenticationError):
            client.get_user("octocat")


def test_user_not_found_is_typed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(request, {"message": "Not Found"}, status=404)

    with _client(handler) as client:
        with pytest.raises(UserNotFoundError):
            client.get_user("ghost")


def test_generic_not_found_is_typed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(request, {"message": "Not Found"}, status=404)

    with _client(handler) as client:
        with pytest.raises(NotFoundError):
            client.get_repository("octocat", "missing-repo")


def test_primary_rate_limit_403_is_typed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1800000000"}
        return httpx.Response(
            403,
            json={"message": "rate limited"},
            headers=headers,
            request=request,
        )

    with _client(handler) as client:
        with pytest.raises(RateLimitError) as excinfo:
            client.get_user("octocat")
    assert excinfo.value.status_code == 403


def test_secondary_rate_limit_429_carries_retry_after() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"message": "Too Many Requests"},
            headers={"Retry-After": "12"},
            request=request,
        )

    with _client(handler) as client:
        with pytest.raises(RateLimitError) as excinfo:
            client.get_user("octocat")
    assert excinfo.value.retry_after == 12.0
    assert excinfo.value.status_code == 429


def test_malformed_json_is_typed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>not json</html>", request=request)

    with _client(handler) as client:
        with pytest.raises(MalformedResponseError):
            client.get_user("octocat")


def test_malformed_list_is_typed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(request, {"not": "a list"})

    with _client(handler) as client:
        with pytest.raises(MalformedResponseError):
            client.list_user_repositories("octocat")


def test_malformed_search_payload_is_typed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(request, {"items": "nope"})

    with _client(handler) as client:
        with pytest.raises(MalformedResponseError):
            client.search_issues("author:octocat")


def test_data_validation_error_carries_context() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(request, {"id": 1, "followers": -5})

    with _client(handler) as client:
        with pytest.raises(DataValidationError) as excinfo:
            client.get_user("octocat")
    assert "login" in excinfo.value.errors[0]


def test_timeout_is_typed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    with _client(handler) as client:
        with pytest.raises(APITimeoutError):
            client.get_user("octocat")


def test_network_error_is_typed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with _client(handler) as client:
        with pytest.raises(NetworkError):
            client.get_user("octocat")


def test_client_is_injectable_and_context_managed(load_raw_fixture: FixtureLoader) -> None:
    transport = httpx.MockTransport(
        lambda request: _json_response(request, load_raw_fixture("user"))
    )
    client = GitHubClient("token", transport=transport)
    assert client.get_user("octocat").login == "octocat"
    client.close()
