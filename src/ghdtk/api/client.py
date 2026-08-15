"""Typed GitHub REST/GraphQL API client.

All data acquisition flows through a single typed HTTP client (issue #17).
The client wraps :mod:`httpx` with token authentication, default headers,
timeouts and an injectable transport so it is fully testable without any
global state.

Every endpoint the product uses has a typed method that returns raw models
(:mod:`ghdtk.models.raw`) — never raw dicts — or raises a typed error from
:mod:`ghdtk.api.errors`. Pagination, rate-limit handling, retries and caching
build on this client in later sub-issues of #16.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, NoReturn, TypeVar

import httpx
from pydantic import BaseModel, SecretStr
from pydantic import ValidationError as PydanticValidationError

from ghdtk.api.errors import (
    APITimeoutError,
    AuthenticationError,
    DataValidationError,
    GitHubAPIError,
    MalformedResponseError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    UserNotFoundError,
)
from ghdtk.models.raw import (
    Commit,
    ContributionCalendar,
    Follower,
    Issue,
    LanguageStats,
    PullRequest,
    Readme,
    Repository,
    Stargazer,
    User,
)

T = TypeVar("T", bound=BaseModel)

GITHUB_API_URL = "https://api.github.com"

DEFAULT_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "github-developer-toolkit",
}

# Preview accept headers needed for extra fields on specific endpoints.
COMMIT_SEARCH_ACCEPT = "application/vnd.github.cloak-preview+json"
STARGAZER_TIMELINE_ACCEPT = "application/vnd.github.star+json"

_GRAPHQL_QUERY = """\
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          firstDay
          contributionDays {
            color
            contributionCount
            date
            weekday
          }
        }
      }
    }
  }
}
"""


def _parse_retry_after(value: str | None) -> float | None:
    """Parse a ``Retry-After`` header (delay seconds or HTTP date)."""
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


class GitHubClient:
    """A thin, typed wrapper around the GitHub REST/GraphQL APIs."""

    def __init__(
        self,
        token: SecretStr | str,
        *,
        base_url: str = GITHUB_API_URL,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        secret = token.get_secret_value() if isinstance(token, SecretStr) else token
        headers = {**DEFAULT_HEADERS, "Authorization": f"Bearer {secret}"}
        self._client = httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
            transport=transport,
        )

    # --- low-level plumbing ------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        request_headers = {**DEFAULT_HEADERS, **(headers or {})}
        try:
            response = self._client.request(
                method,
                path,
                params=params,
                headers=request_headers,
                json=json_body,
            )
        except httpx.TimeoutException as exc:
            raise APITimeoutError(f"Request timed out: {method} {path}") from exc
        except httpx.TransportError as exc:
            raise NetworkError(f"Network error for {method} {path}: {exc}") from exc
        if response.is_success:
            return response
        self._raise_for_status(response)

    def _raise_for_status(self, response: httpx.Response) -> NoReturn:
        """Raise the typed error matching an unsuccessful response."""
        status = response.status_code
        path = response.request.url.path
        if status == 401:
            raise AuthenticationError(
                "GitHub authentication failed; check your token and its scopes."
            )
        if status == 404:
            if path.startswith("/users/"):
                raise UserNotFoundError(f"GitHub user not found: {path}")
            raise NotFoundError(f"GitHub resource not found: {path}")
        if status == 429 or self._primary_limit_exhausted(response):
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            reset_at = self._rate_limit_reset(response)
            raise RateLimitError(
                "GitHub rate limit reached; retry after the limit resets.",
                status_code=status,
                retry_after=retry_after,
                reset_at=reset_at,
            )
        if status == 403:
            raise AuthenticationError(
                f"GitHub request forbidden (403) for {path}; the token may lack scope."
            )
        error = GitHubAPIError(f"GitHub API error {status}: {path}")
        error.status_code = status
        raise error

    @staticmethod
    def _primary_limit_exhausted(response: httpx.Response) -> bool:
        return response.status_code == 403 and (
            response.headers.get("X-RateLimit-Remaining") == "0"
            or response.headers.get("X-RateLimit-Reset") is not None
        )

    @staticmethod
    def _rate_limit_reset(response: httpx.Response) -> datetime | None:
        value = response.headers.get("X-RateLimit-Reset")
        if value is None:
            return None
        try:
            return datetime.fromtimestamp(int(value), tz=UTC)
        except (ValueError, OSError):
            return None

    @staticmethod
    def _json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise MalformedResponseError(
                f"Malformed JSON from {response.request.url}: {exc}"
            ) from exc

    def _validate_payload(self, model: type[T], payload: Any, *, endpoint: str) -> T:
        try:
            return model.model_validate(payload)
        except PydanticValidationError as exc:
            errors = [
                f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
                for item in exc.errors()
            ]
            raise DataValidationError(
                f"Invalid {model.__name__} payload from {endpoint}",
                endpoint=endpoint,
                errors=errors,
            ) from exc

    def _deserialize(self, response: httpx.Response, model: type[T]) -> T:
        return self._validate_payload(model, self._json(response), endpoint=str(response.url))

    def _deserialize_list(self, response: httpx.Response, model: type[T]) -> list[T]:
        payload = self._json(response)
        if not isinstance(payload, list):
            raise MalformedResponseError(
                f"Expected a list from {response.request.url}, got {type(payload).__name__}"
            )
        endpoint = str(response.url)
        return [self._validate_payload(model, item, endpoint=endpoint) for item in payload]

    def _search_items(self, response: httpx.Response, model: type[T]) -> list[T]:
        payload = self._json(response)
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise MalformedResponseError(
                f"Expected a search payload with an items list from {response.request.url}"
            )
        endpoint = str(response.url)
        return [self._validate_payload(model, item, endpoint=endpoint) for item in payload["items"]]

    def _paginated_get(
        self,
        path: str,
        model: type[T],
        *,
        params: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> list[T]:
        response = self._request("GET", path, params=params, headers=headers)
        return self._deserialize_list(response, model)

    # --- user endpoints ----------------------------------------------------

    def get_user(self, username: str) -> User:
        """Fetch ``GET /users/{username}`` as a :class:`User`."""
        return self._deserialize(self._request("GET", f"/users/{username}"), User)

    def get_authenticated_user(self) -> User:
        """Fetch ``GET /user`` (the authenticated token's owner)."""
        return self._deserialize(self._request("GET", "/user"), User)

    def list_user_repositories(
        self,
        username: str,
        *,
        per_page: int = 100,
        page: int = 1,
    ) -> list[Repository]:
        """Fetch one page of ``GET /users/{username}/repos``."""
        return self._paginated_get(
            f"/users/{username}/repos",
            Repository,
            params={"per_page": per_page, "page": page},
        )

    # --- repository endpoints ----------------------------------------------

    def get_repository(self, owner: str, repo: str) -> Repository:
        """Fetch ``GET /repos/{owner}/{repo}`` as a :class:`Repository`."""
        return self._deserialize(self._request("GET", f"/repos/{owner}/{repo}"), Repository)

    def get_languages(self, owner: str, repo: str) -> LanguageStats:
        """Fetch ``GET /repos/{owner}/{repo}/languages``."""
        response = self._request("GET", f"/repos/{owner}/{repo}/languages")
        return self._validate_payload(
            LanguageStats, self._json(response), endpoint=str(response.url)
        )

    def get_readme(self, owner: str, repo: str) -> Readme | None:
        """Fetch ``GET /repos/{owner}/{repo}/readme``, or ``None`` when absent."""
        try:
            response = self._request("GET", f"/repos/{owner}/{repo}/readme")
        except NotFoundError:
            return None
        return self._deserialize(response, Readme)

    def list_commits(
        self,
        owner: str,
        repo: str,
        *,
        author: str | None = None,
        per_page: int = 100,
        page: int = 1,
    ) -> list[Commit]:
        """Fetch one page of ``GET /repos/{owner}/{repo}/commits``."""
        params: dict[str, Any] = {"per_page": per_page, "page": page}
        if author is not None:
            params["author"] = author
        return self._paginated_get(f"/repos/{owner}/{repo}/commits", Commit, params=params)

    def list_pull_requests(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "all",
        per_page: int = 100,
        page: int = 1,
    ) -> list[PullRequest]:
        """Fetch one page of ``GET /repos/{owner}/{repo}/pulls``."""
        return self._paginated_get(
            f"/repos/{owner}/{repo}/pulls",
            PullRequest,
            params={"state": state, "per_page": per_page, "page": page},
        )

    def list_issues(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "all",
        per_page: int = 100,
        page: int = 1,
    ) -> list[Issue]:
        """Fetch one page of ``GET /repos/{owner}/{repo}/issues``."""
        return self._paginated_get(
            f"/repos/{owner}/{repo}/issues",
            Issue,
            params={"state": state, "per_page": per_page, "page": page},
        )

    def list_followers(
        self,
        username: str,
        *,
        per_page: int = 100,
        page: int = 1,
    ) -> list[Follower]:
        """Fetch one page of ``GET /users/{username}/followers``."""
        return self._paginated_get(
            f"/users/{username}/followers",
            Follower,
            params={"per_page": per_page, "page": page},
        )

    def list_stargazers(
        self,
        owner: str,
        repo: str,
        *,
        per_page: int = 100,
        page: int = 1,
    ) -> list[Stargazer]:
        """Fetch one page of ``GET /repos/{owner}/{repo}/stargazers``.

        Uses the timeline preview header so ``starred_at`` is populated.
        """
        return self._paginated_get(
            f"/repos/{owner}/{repo}/stargazers",
            Stargazer,
            params={"per_page": per_page, "page": page},
            headers={"Accept": STARGAZER_TIMELINE_ACCEPT},
        )

    # --- search endpoints --------------------------------------------------

    def search_commits(
        self,
        query: str,
        *,
        per_page: int = 100,
        page: int = 1,
    ) -> list[Commit]:
        """Search commits via ``GET /search/commits``."""
        response = self._request(
            "GET",
            "/search/commits",
            params={"q": query, "per_page": per_page, "page": page},
            headers={"Accept": COMMIT_SEARCH_ACCEPT},
        )
        return self._search_items(response, Commit)

    def search_pull_requests(
        self,
        query: str,
        *,
        per_page: int = 100,
        page: int = 1,
    ) -> list[PullRequest]:
        """Search pull requests via ``GET /search/issues`` (PR items)."""
        response = self._request(
            "GET",
            "/search/issues",
            params={"q": query, "per_page": per_page, "page": page},
        )
        return self._search_items(response, PullRequest)

    def search_issues(
        self,
        query: str,
        *,
        per_page: int = 100,
        page: int = 1,
    ) -> list[Issue]:
        """Search issues via ``GET /search/issues``."""
        response = self._request(
            "GET",
            "/search/issues",
            params={"q": query, "per_page": per_page, "page": page},
        )
        return self._search_items(response, Issue)

    # --- GraphQL -----------------------------------------------------------

    def get_contribution_calendar(self, username: str) -> ContributionCalendar:
        """Fetch the user's contribution calendar via the GraphQL API."""
        response = self._request(
            "POST",
            "/graphql",
            json_body={"query": _GRAPHQL_QUERY, "variables": {"login": username}},
        )
        data = self._json(response)
        try:
            user = data["data"]["user"]
        except (KeyError, TypeError) as exc:
            raise MalformedResponseError(f"Unexpected GraphQL payload for {username}") from exc
        if user is None:
            raise UserNotFoundError(f"GitHub user not found: {username}")
        try:
            calendar = user["contributionsCollection"]["contributionCalendar"]
        except (KeyError, TypeError) as exc:
            raise MalformedResponseError(f"Missing contribution calendar for {username}") from exc
        return self._validate_payload(ContributionCalendar, calendar, endpoint="/graphql")

    # --- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def create_client(
    token: SecretStr | str,
    *,
    base_url: str = GITHUB_API_URL,
    timeout: float = 30.0,
    transport: httpx.BaseTransport | None = None,
) -> GitHubClient:
    """Create a :class:`GitHubClient` for the given token and base URL."""
    return GitHubClient(
        token,
        base_url=base_url,
        timeout=timeout,
        transport=transport,
    )


__all__ = [
    "COMMIT_SEARCH_ACCEPT",
    "DEFAULT_HEADERS",
    "GITHUB_API_URL",
    "STARGAZER_TIMELINE_ACCEPT",
    "GitHubClient",
    "create_client",
]
