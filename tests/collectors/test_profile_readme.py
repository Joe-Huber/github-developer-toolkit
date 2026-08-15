"""Unit tests for profile README retrieval (issue #25).

The profile README lives in the ``<username>/<username>`` repository. These
tests exercise the distinct typed states the collector produces: a present
README, a missing profile repository, a repository without a README, an empty
README, and a fetch failure.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

from ghdtk.api.client import create_client
from ghdtk.api.rate_limit import BackoffPolicy
from ghdtk.collectors import collect_profile_readme
from ghdtk.models.raw import ProfileReadmeStatus, Repository


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


def _handler(routes: dict[str, tuple[int, Any]], log: list[str] | None = None) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        if log is not None:
            log.append(request.url.path)
        status, payload = routes.get(request.url.path, (404, {"message": "Not Found"}))
        return httpx.Response(status, json=payload, request=request)

    return handler


def _profile_repository(username: str = "octocat") -> Repository:
    return Repository(name=username, full_name=f"{username}/{username}")


def _readme_payload(text: str) -> dict[str, Any]:
    return {
        "type": "file",
        "encoding": "base64",
        "size": len(text),
        "name": "README.md",
        "path": "README.md",
        "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
    }


def test_present_readme() -> None:
    routes = {
        "/repos/octocat/octocat/readme": (200, _readme_payload("# Hi there\n\nI build things.")),
    }
    repositories = [Repository.model_validate(_profile_repository())]
    with _client(_handler(routes)) as client:
        result = collect_profile_readme(client, "octocat", repositories=repositories)

    assert result.status == ProfileReadmeStatus.PRESENT
    assert result.content == "# Hi there\n\nI build things."
    assert result.repository == "octocat/octocat"


def test_present_readme_matches_case_insensitively() -> None:
    routes = {
        "/repos/octocat/octocat/readme": (200, _readme_payload("# Hi")),
    }
    repositories = [Repository.model_validate(_profile_repository("OctoCat"))]
    with _client(_handler(routes)) as client:
        result = collect_profile_readme(client, "octocat", repositories=repositories)

    assert result.status == ProfileReadmeStatus.PRESENT
    assert result.repository == "octocat/octocat"


def test_no_profile_repository() -> None:
    repositories = [Repository(name="Hello-World", full_name="octocat/Hello-World")]
    with _client(_handler({})) as client:
        result = collect_profile_readme(client, "octocat", repositories=repositories)

    assert result.status == ProfileReadmeStatus.NO_PROFILE_REPO
    assert result.content is None
    assert result.repository is None


def test_no_readme() -> None:
    routes = {"/repos/octocat/octocat/readme": (404, {"message": "Not Found"})}
    repositories = [Repository.model_validate(_profile_repository())]
    with _client(_handler(routes)) as client:
        result = collect_profile_readme(client, "octocat", repositories=repositories)

    assert result.status == ProfileReadmeStatus.NO_README


def test_empty_readme() -> None:
    routes = {
        "/repos/octocat/octocat/readme": (200, _readme_payload("   \n  ")),
    }
    repositories = [Repository.model_validate(_profile_repository())]
    with _client(_handler(routes)) as client:
        result = collect_profile_readme(client, "octocat", repositories=repositories)

    assert result.status == ProfileReadmeStatus.EMPTY


def test_fetch_failed() -> None:
    routes = {"/repos/octocat/octocat/readme": (500, {"message": "boom"})}
    repositories = [Repository.model_validate(_profile_repository())]
    with _client(_handler(routes)) as client:
        result = collect_profile_readme(client, "octocat", repositories=repositories)

    assert result.status == ProfileReadmeStatus.FETCH_FAILED
    assert result.reason is not None


def test_fetches_repositories_when_not_provided() -> None:
    routes = {
        "/users/octocat/repos": (200, [_profile_repository().model_dump(mode="json")]),
        "/repos/octocat/octocat/readme": (200, _readme_payload("# Hi")),
    }
    log: list[str] = []
    with _client(_handler(routes, log=log)) as client:
        result = collect_profile_readme(client, "octocat")

    assert result.status == ProfileReadmeStatus.PRESENT
    assert "/users/octocat/repos" in log
    assert "/repos/octocat/octocat/readme" in log
