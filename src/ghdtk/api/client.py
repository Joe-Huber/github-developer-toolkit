"""Typed GitHub REST/GraphQL API client.

All data acquisition flows through a single typed HTTP client (issue #17).
The client wraps :mod:`httpx` with token authentication, default headers,
timeouts and an injectable transport so it is fully testable without any
global state.

On top of the typed endpoint methods, the client provides automatic
pagination (issue #18): list and search methods walk every page of a dataset
via ``Link`` headers, with a ``max_pages`` guard. Primary rate-limit tracking
pauses before a request when the budget is exhausted, and secondary 403/429
responses are retried with exponential backoff + jitter before surfacing a
typed :class:`~ghdtk.api.errors.RateLimitError`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, SecretStr
from pydantic import ValidationError as PydanticValidationError

from ghdtk.api.cache import (
    CachedResponse,
    ResponseCache,
    _entry_to_response,
    cache_key,
    default_cache_directory,
)
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
from ghdtk.api.normalizers import validate_sanity
from ghdtk.api.pagination import next_page_url
from ghdtk.api.rate_limit import BackoffPolicy, RateLimitState, parse_retry_after
from ghdtk.models.raw import (
    BaseRawModel,
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
      restrictedContributionsCount
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

_RETRYABLE_STATUS = frozenset({403, 429})


class GitHubClient:
    """A thin, typed wrapper around the GitHub REST/GraphQL APIs."""

    def __init__(
        self,
        token: SecretStr | str,
        *,
        base_url: str = GITHUB_API_URL,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        per_page: int = 100,
        max_retries: int = 3,
        backoff: BackoffPolicy | None = None,
        cache: ResponseCache | None = None,
    ) -> None:
        secret = token.get_secret_value() if isinstance(token, SecretStr) else token
        headers = {**DEFAULT_HEADERS, "Authorization": f"Bearer {secret}"}
        self._client = httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
            transport=transport,
        )
        self._per_page = per_page
        self._max_retries = max_retries
        self._backoff = backoff if backoff is not None else BackoffPolicy()
        self._rate_limit = RateLimitState()
        self._requests_made = 0
        self._cache = cache

    @classmethod
    def from_settings(cls, settings: Any) -> GitHubClient:
        """Build a client from a :class:`ghdtk.config.Settings` instance."""
        from ghdtk.config.settings import Settings

        assert isinstance(settings, Settings)
        cache: ResponseCache | None = None
        if settings.cache_enabled:
            from ghdtk.api.cache import DiskCache

            directory = settings.cache_dir or default_cache_directory()
            cache = ResponseCache(
                DiskCache(directory),
                ttl_seconds=settings.cache_ttl_seconds,
            )
        return cls(
            settings.github_token,
            base_url=settings.github_base_url,
            timeout=settings.github_timeout_seconds,
            per_page=settings.github_per_page,
            max_retries=settings.github_max_retries,
            cache=cache,
        )

    # --- introspection -----------------------------------------------------

    @property
    def requests_made(self) -> int:
        """Number of HTTP requests sent (retries count)."""
        return self._requests_made

    @property
    def rate_limit(self) -> RateLimitState:
        """The primary rate-limit budget observed so far."""
        return self._rate_limit

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
        cache = self._cache
        key: str | None = None
        entry: CachedResponse | None = None
        url = path
        if cache is not None and method == "GET":
            url = str(
                self._client.build_request("GET", path, params=params, headers=request_headers).url
            )
            key = cache_key(method, url)
            entry = cache.get(key)
            if entry is not None:
                if cache.is_fresh(entry):
                    return _entry_to_response(entry, url=url)
                if entry.etag is not None:
                    request_headers["If-None-Match"] = entry.etag

        self._wait_for_rate_limit()
        attempts = 0
        while True:
            attempts += 1
            self._requests_made += 1
            try:
                response = self._client.request(
                    method,
                    path,
                    params=params,
                    headers=request_headers,
                    json=json_body,
                )
            except httpx.TimeoutException as exc:
                if attempts >= self._max_retries:
                    raise APITimeoutError(f"Request timed out: {method} {path}") from exc
                self._backoff.sleep(self._backoff.delay(attempts))
                continue
            except httpx.TransportError as exc:
                if attempts >= self._max_retries:
                    raise NetworkError(f"Network error for {method} {path}: {exc}") from exc
                self._backoff.sleep(self._backoff.delay(attempts))
                continue

            self._rate_limit.update_from(response)
            if (
                response.status_code == 304
                and cache is not None
                and key is not None
                and entry is not None
            ):
                refreshed = cache.revalidate(key, entry)
                return _entry_to_response(refreshed, url=url)
            if response.is_success:
                if key is not None and response.status_code == 200 and cache is not None:
                    cache.set(key, response, url)
                return response

            # Secondary rate limit (abuse): retry with Retry-After / backoff.
            if response.status_code in _RETRYABLE_STATUS and not self._primary_limit_exhausted(
                response
            ):
                if attempts >= self._max_retries:
                    self._raise_for_status(response)
                retry_after = parse_retry_after(response.headers.get("Retry-After"))
                if retry_after is None:
                    delay = self._backoff.delay(attempts)
                else:
                    delay = min(retry_after, self._backoff.max_delay)
                self._backoff.sleep(delay)
                continue

            self._raise_for_status(response)

    def _raise_for_status(self, response: httpx.Response) -> Any:
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
            retry_after = parse_retry_after(response.headers.get("Retry-After"))
            reset_at = self._rate_limit_reset(response)
            raise RateLimitError(
                "GitHub rate limit reached; retry after the limit resets.",
                status_code=status,
                retry_after=retry_after,
                reset_at=reset_at,
            )
        if status == 403 and response.headers.get("Retry-After") is not None:
            retry_after = parse_retry_after(response.headers.get("Retry-After"))
            raise RateLimitError(
                "GitHub secondary rate limit reached; retry after the backoff.",
                status_code=403,
                retry_after=retry_after,
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

    def _wait_for_rate_limit(self) -> None:
        """Pause when the primary budget is exhausted, or fail predictably."""
        wait = self._rate_limit.wait_seconds()
        if wait <= 0:
            return
        if wait <= self._backoff.max_delay:
            self._backoff.sleep(wait)
            return
        raise RateLimitError(
            "GitHub primary rate limit exhausted; "
            f"resets in {int(wait)}s. Retry later or use a higher-limit token.",
            status_code=403,
            reset_at=self._rate_limit.reset_at,
        )

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
            value = model.model_validate(payload)
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
        if isinstance(value, BaseRawModel):
            validate_sanity(value, endpoint=endpoint)
        return value

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

    def _paginate_all(
        self,
        path: str,
        model: type[T],
        *,
        params: dict[str, Any],
        headers: dict[str, str] | None = None,
        search: bool = False,
        max_pages: int | None = None,
    ) -> list[T]:
        """Collect every page of a list/search endpoint into one typed list."""
        items: list[T] = []
        current_path = path
        current_params: dict[str, Any] | None = {"page": 1, **params}
        pages = 0
        while True:
            if max_pages is not None and pages >= max_pages:
                break
            response = self._request("GET", current_path, params=current_params, headers=headers)
            pages += 1
            page_items = (
                self._search_items(response, model)
                if search
                else self._deserialize_list(response, model)
            )
            items.extend(page_items)
            next_url = next_page_url(response)
            if next_url is None:
                break
            current_path = next_url
            current_params = None
        return items

    def _default_per_page(self, per_page: int | None) -> int:
        return self._per_page if per_page is None else per_page

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
        per_page: int | None = None,
        max_pages: int | None = None,
    ) -> list[Repository]:
        """Fetch every page of ``GET /users/{username}/repos``."""
        return self._paginate_all(
            f"/users/{username}/repos",
            Repository,
            params={"per_page": self._default_per_page(per_page)},
            max_pages=max_pages,
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
        per_page: int | None = None,
        max_pages: int | None = None,
    ) -> list[Commit]:
        """Fetch every page of ``GET /repos/{owner}/{repo}/commits``."""
        params: dict[str, Any] = {"per_page": self._default_per_page(per_page)}
        if author is not None:
            params["author"] = author
        return self._paginate_all(
            f"/repos/{owner}/{repo}/commits",
            Commit,
            params=params,
            max_pages=max_pages,
        )

    def list_pull_requests(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "all",
        per_page: int | None = None,
        max_pages: int | None = None,
    ) -> list[PullRequest]:
        """Fetch every page of ``GET /repos/{owner}/{repo}/pulls``."""
        return self._paginate_all(
            f"/repos/{owner}/{repo}/pulls",
            PullRequest,
            params={"state": state, "per_page": self._default_per_page(per_page)},
            max_pages=max_pages,
        )

    def list_issues(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "all",
        per_page: int | None = None,
        max_pages: int | None = None,
    ) -> list[Issue]:
        """Fetch every page of ``GET /repos/{owner}/{repo}/issues``."""
        return self._paginate_all(
            f"/repos/{owner}/{repo}/issues",
            Issue,
            params={"state": state, "per_page": self._default_per_page(per_page)},
            max_pages=max_pages,
        )

    def list_followers(
        self,
        username: str,
        *,
        per_page: int | None = None,
        max_pages: int | None = None,
    ) -> list[Follower]:
        """Fetch every page of ``GET /users/{username}/followers``."""
        return self._paginate_all(
            f"/users/{username}/followers",
            Follower,
            params={"per_page": self._default_per_page(per_page)},
            max_pages=max_pages,
        )

    def list_following(
        self,
        username: str,
        *,
        per_page: int | None = None,
        max_pages: int | None = None,
    ) -> list[Follower]:
        """Fetch every page of ``GET /users/{username}/following``.

        The payload shape is identical to the followers endpoint, so the
        :class:`~ghdtk.models.raw.Follower` model is reused.
        """
        return self._paginate_all(
            f"/users/{username}/following",
            Follower,
            params={"per_page": self._default_per_page(per_page)},
            max_pages=max_pages,
        )

    def list_stargazers(
        self,
        owner: str,
        repo: str,
        *,
        per_page: int | None = None,
        max_pages: int | None = None,
    ) -> list[Stargazer]:
        """Fetch every page of ``GET /repos/{owner}/{repo}/stargazers``.

        Uses the timeline preview header so ``starred_at`` is populated.
        """
        return self._paginate_all(
            f"/repos/{owner}/{repo}/stargazers",
            Stargazer,
            params={"per_page": self._default_per_page(per_page)},
            headers={"Accept": STARGAZER_TIMELINE_ACCEPT},
            max_pages=max_pages,
        )

    # --- search endpoints --------------------------------------------------

    def search_commits(
        self,
        query: str,
        *,
        per_page: int | None = None,
        max_pages: int | None = None,
    ) -> list[Commit]:
        """Search commits via ``GET /search/commits``."""
        return self._paginate_all(
            "/search/commits",
            Commit,
            params={"q": query, "per_page": self._default_per_page(per_page)},
            headers={"Accept": COMMIT_SEARCH_ACCEPT},
            search=True,
            max_pages=max_pages,
        )

    def search_pull_requests(
        self,
        query: str,
        *,
        per_page: int | None = None,
        max_pages: int | None = None,
    ) -> list[PullRequest]:
        """Search pull requests via ``GET /search/issues`` (PR items)."""
        return self._paginate_all(
            "/search/issues",
            PullRequest,
            params={"q": query, "per_page": self._default_per_page(per_page)},
            search=True,
            max_pages=max_pages,
        )

    def search_issues(
        self,
        query: str,
        *,
        per_page: int | None = None,
        max_pages: int | None = None,
    ) -> list[Issue]:
        """Search issues via ``GET /search/issues``."""
        return self._paginate_all(
            "/search/issues",
            Issue,
            params={"q": query, "per_page": self._default_per_page(per_page)},
            search=True,
            max_pages=max_pages,
        )

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
        if isinstance(calendar, dict):
            restricted = user["contributionsCollection"].get("restrictedContributionsCount")
            if restricted is not None:
                calendar = {**calendar, "restrictedContributionsCount": restricted}
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
    per_page: int = 100,
    max_retries: int = 3,
    backoff: BackoffPolicy | None = None,
    cache: ResponseCache | None = None,
) -> GitHubClient:
    """Create a :class:`GitHubClient` for the given token and base URL."""
    return GitHubClient(
        token,
        base_url=base_url,
        timeout=timeout,
        transport=transport,
        per_page=per_page,
        max_retries=max_retries,
        backoff=backoff,
        cache=cache,
    )


__all__ = [
    "COMMIT_SEARCH_ACCEPT",
    "DEFAULT_HEADERS",
    "GITHUB_API_URL",
    "STARGAZER_TIMELINE_ACCEPT",
    "GitHubClient",
    "create_client",
]
