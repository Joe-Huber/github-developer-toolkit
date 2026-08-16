"""Corpus generator for recorded GitHub API responses (issue #59).

Builds the versioned fixture corpus under ``tests/fixtures/corpus/``: one
``session.json`` per profile plus an index ``MANIFEST.json``. Every session is a
deterministic recording of the requests the collection orchestrator makes for
that profile and the responses it should receive, so tests can replay a full
collection without ever touching the live API.

Regenerating the corpus is a deliberate step::

    python tests/fixtures/generate_corpus.py

The payloads are built from small base builders so the corpus stays coherent —
repositories referenced by a commit, pull request or stargazer entry always
exist in the profile's repository list.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

CORPUS_DIR = Path(__file__).parent / "corpus"
CORPUS_VERSION = 1
API_BASE = "https://api.github.com"
NOW = "2026-01-01T12:00:00Z"

_OBJECT_ID = 1000


def _next_id() -> int:
    global _OBJECT_ID
    _OBJECT_ID += 1
    return _OBJECT_ID


def _owner(login: str) -> dict[str, Any]:
    return {
        "login": login,
        "id": _next_id(),
        "node_id": f"MDQ6VXNlcntidF90_#!_id_{login}",
        "avatar_url": f"https://avatars.githubusercontent.com/u/{_next_id()}?v=4",
        "html_url": f"https://github.com/{login}",
        "type": "User",
        "site_admin": False,
    }


def _user_payload(login: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "login": login,
        "id": _next_id(),
        "node_id": f"MDQ6VXNlci{login}",
        "avatar_url": f"https://avatars.githubusercontent.com/u/{_next_id()}?v=4",
        "html_url": f"https://github.com/{login}",
        "url": f"{API_BASE}/users/{login}",
        "followers_url": f"{API_BASE}/users/{login}/followers",
        "following_url": f"{API_BASE}/users/{login}/following",
        "repos_url": f"{API_BASE}/users/{login}/repos",
        "type": "User",
        "site_admin": False,
        "name": None,
        "company": None,
        "blog": None,
        "location": None,
        "email": None,
        "hireable": None,
        "bio": None,
        "twitter_username": None,
        "public_repos": 0,
        "public_gists": 0,
        "followers": 0,
        "following": 0,
        "created_at": "2015-01-01T00:00:00Z",
        "updated_at": "2025-12-01T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def _repo_payload(
    owner: str,
    name: str,
    *,
    stars: int = 0,
    fork: bool = False,
    archived: bool = False,
    description: str | None = None,
    topics: list[str] | None = None,
    license_key: str | None = None,
    homepage: str | None = None,
    language: str | None = None,
    created_at: str,
    pushed_at: str,
) -> dict[str, Any]:
    full_name = f"{owner}/{name}"
    payload: dict[str, Any] = {
        "id": _next_id(),
        "node_id": f"MDEwOlJlcG9zaXRvcnk{name}",
        "name": name,
        "full_name": full_name,
        "private": False,
        "owner": _owner(owner),
        "html_url": f"https://github.com/{full_name}",
        "url": f"{API_BASE}/repos/{full_name}",
        "description": description,
        "fork": fork,
        "created_at": created_at,
        "updated_at": pushed_at,
        "pushed_at": pushed_at,
        "homepage": homepage,
        "size": 100,
        "stargazers_count": stars,
        "watchers_count": stars,
        "language": language,
        "has_issues": True,
        "has_projects": True,
        "has_downloads": True,
        "has_wiki": True,
        "has_pages": False,
        "has_discussions": False,
        "forks_count": 3,
        "archived": archived,
        "disabled": False,
        "open_issues_count": 0,
        "license": None
        if license_key is None
        else {"key": license_key, "name": license_key, "spdx_id": license_key},
        "topics": topics or [],
        "visibility": "public",
        "default_branch": "main",
        "allow_forking": True,
        "is_template": False,
        "web_commit_signoff_required": False,
    }
    return payload


def _readme_payload(owner: str, repo: str, text: str) -> dict[str, Any]:
    content = base64.b64encode(text.encode("utf-8")).decode("ascii")
    full_name = f"{owner}/{repo}"
    return {
        "type": "file",
        "encoding": "base64",
        "size": len(content),
        "name": "README.md",
        "path": "README.md",
        "content": content,
        "sha": "3d21ec53a331a6f037a91c368710b99387d012c1",
        "url": f"{API_BASE}/repos/{full_name}/contents/README.md",
        "html_url": f"https://github.com/{full_name}/blob/main/README.md",
        "git_url": f"{API_BASE}/repos/{full_name}/git/blobs/3d21ec53",
        "download_url": f"https://raw.githubusercontent.com/{full_name}/main/README.md",
    }


def _commit_payload(
    login: str,
    name: str,
    email: str,
    sha: str,
    *,
    date: str,
    message: str,
) -> dict[str, Any]:
    return {
        "sha": sha,
        "commit": {
            "author": {"name": name, "email": email, "date": date},
            "committer": {"name": name, "email": email, "date": date},
            "message": message,
            "url": f"{API_BASE}/repos/{login}/{name}/git/commits/{sha}",
            "comment_count": 0,
        },
        "url": f"{API_BASE}/repos/{login}/{name}/commits/{sha}",
        "html_url": f"https://github.com/{login}/{name}/commit/{sha}",
        "comments_url": f"{API_BASE}/repos/{login}/{name}/commits/{sha}/comments",
        "author": _owner(login),
        "committer": _owner(login),
        "parents": [],
    }


def _pr_payload(
    owner: str,
    repo: str,
    number: int,
    title: str,
    *,
    state: str,
    merged: bool = False,
    created_at: str,
    closed_at: str | None = None,
    merged_at: str | None = None,
    comments: int = 0,
    review_comments: int = 0,
) -> dict[str, Any]:
    full_name = f"{owner}/{repo}"
    return {
        "url": f"{API_BASE}/repos/{full_name}/pulls/{number}",
        "id": _next_id(),
        "html_url": f"https://github.com/{full_name}/pull/{number}",
        "diff_url": f"https://github.com/{full_name}/pull/{number}.diff",
        "patch_url": f"https://github.com/{full_name}/pull/{number}.patch",
        "issue_url": f"{API_BASE}/repos/{full_name}/issues/{number}",
        "repository_url": f"{API_BASE}/repos/{full_name}",
        "number": number,
        "state": state,
        "locked": False,
        "title": title,
        "user": _owner(owner),
        "body": "A contribution.",
        "created_at": created_at,
        "updated_at": closed_at or created_at,
        "closed_at": closed_at,
        "merged_at": merged_at,
        "merge_commit_sha": "cd9af0783ad2d4fe2d1d8e9b2c4b3d2f1e5f6a7b" if merged else None,
        "assignee": None,
        "assignees": [],
        "requested_reviewers": [],
        "labels": [],
        "draft": False,
        "comments": comments,
        "review_comments": review_comments,
        "maintainer_can_modify": False,
        "commits": 1,
        "additions": 10,
        "deletions": 2,
        "changed_files": 3,
        "merged": merged,
        "mergeable": True,
        "rebaseable": True,
        "mergeable_state": "clean" if merged else "draft",
        "merged_by": None if not merged else _owner(owner),
        "head": {"label": f"{owner}:feat/{number}", "ref": f"feat/{number}", "sha": "a" * 40},
        "base": {"label": f"{owner}:main", "ref": "main", "sha": "b" * 40},
        "author_association": "OWNER",
    }


def _pr_search_item(
    owner: str,
    repo: str,
    number: int,
    title: str,
    *,
    state: str,
    merged: bool = False,
    created_at: str,
    closed_at: str | None = None,
    merged_at: str | None = None,
    comments: int = 0,
    review_comments: int = 0,
) -> dict[str, Any]:
    full_name = f"{owner}/{repo}"
    return {
        "url": f"{API_BASE}/repos/{full_name}/issues/{number}",
        "repository_url": f"{API_BASE}/repos/{full_name}",
        "labels_url": f"{API_BASE}/repos/{full_name}/issues/{number}/labels{{/name}}",
        "comments_url": f"{API_BASE}/repos/{full_name}/issues/{number}/comments",
        "events_url": f"{API_BASE}/repos/{full_name}/issues/{number}/events",
        "html_url": f"https://github.com/{full_name}/pull/{number}",
        "id": _next_id(),
        "number": number,
        "title": title,
        "user": _owner(owner),
        "labels": [],
        "state": state,
        "locked": False,
        "assignee": None,
        "assignees": [],
        "milestone": None,
        "comments": comments,
        "created_at": created_at,
        "updated_at": closed_at or created_at,
        "closed_at": closed_at,
        "author_association": "OWNER",
        "active_lock_reason": None,
        "draft": False,
        "pull_request": {
            "url": f"{API_BASE}/repos/{full_name}/pulls/{number}",
            "html_url": f"https://github.com/{full_name}/pull/{number}",
            "diff_url": f"https://github.com/{full_name}/pull/{number}.diff",
            "patch_url": f"https://github.com/{full_name}/pull/{number}.patch",
            "merged_at": merged_at,
            "merged": merged,
            "review_comments": review_comments,
            "comments": comments,
        },
    }


def _issue_payload(
    owner: str,
    repo: str,
    number: int,
    title: str,
    *,
    state: str,
    created_at: str,
    closed_at: str | None = None,
    comments: int = 0,
) -> dict[str, Any]:
    full_name = f"{owner}/{repo}"
    return {
        "id": _next_id(),
        "node_id": f"MDU6SXNzdWU{number}",
        "url": f"{API_BASE}/repos/{full_name}/issues/{number}",
        "repository_url": f"{API_BASE}/repos/{full_name}",
        "labels_url": f"{API_BASE}/repos/{full_name}/issues/{number}/labels{{/name}}",
        "comments_url": f"{API_BASE}/repos/{full_name}/issues/{number}/comments",
        "events_url": f"{API_BASE}/repos/{full_name}/issues/{number}/events",
        "html_url": f"https://github.com/{full_name}/issues/{number}",
        "number": number,
        "state": state,
        "title": title,
        "body": "An issue body.",
        "user": _owner(owner),
        "labels": [],
        "assignee": None,
        "assignees": [],
        "milestone": None,
        "locked": False,
        "comments": comments,
        "created_at": created_at,
        "updated_at": closed_at or created_at,
        "closed_at": closed_at,
        "author_association": "OWNER",
    }


def _follower_payload(login: str) -> dict[str, Any]:
    return {
        "login": login,
        "id": _next_id(),
        "node_id": f"MDQ6VXNlcjEw{login}",
        "avatar_url": f"https://avatars.githubusercontent.com/u/{_next_id()}?v=4",
        "html_url": f"https://github.com/{login}",
        "type": "User",
        "site_admin": False,
    }


def _stargazer_payload(login: str, starred_at: str) -> dict[str, Any]:
    payload = _follower_payload(login)
    payload["starred_at"] = starred_at
    return payload


def _calendar_payload(total: int, weeks: list[dict[str, Any]]) -> dict[str, Any]:
    return {"totalContributions": total, "weeks": weeks}


def _week(first_day: str, days: list[tuple[str, int]]) -> dict[str, Any]:
    return {
        "firstDay": first_day,
        "contributionDays": [
            {
                "color": "#39d353" if count else "#ebedf0",
                "contributionCount": count,
                "date": date,
                "weekday": _weekday(date),
            }
            for date, count in days
        ],
    }


def _weekday(date_iso: str) -> int:
    from datetime import date as DateType

    return DateType.fromisoformat(date_iso).weekday()


def _calendar(entries: list[tuple[str, int]]) -> dict[str, Any]:
    """Build a calendar payload from (date, count) pairs, grouped by week."""
    weeks: dict[str, list[tuple[str, int]]] = {}
    for date_iso, count in entries:
        weeks.setdefault(date_iso[:10], []).append((date_iso, count))
    return _calendar_payload(
        total=sum(count for _, count in entries),
        weeks=[_week(first_day, days) for first_day, days in sorted(weeks.items())],
    )


def _link(next_path: str) -> str:
    return f'<{API_BASE}{next_path}>; rel="next"'


def _entry(
    method: str,
    path: str,
    params: dict[str, str] | None = None,
    *,
    status: int = 200,
    body: Any = None,
    content: str | None = None,
    link_next: str | None = None,
    rate_limit_remaining: int | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {"status": status}
    if body is not None:
        response["body"] = body
    if content is not None:
        response["content"] = content
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if link_next is not None:
        headers["Link"] = link_next
    if rate_limit_remaining is not None:
        headers["X-RateLimit-Remaining"] = str(rate_limit_remaining)
        headers["X-RateLimit-Limit"] = "5000"
        headers["X-RateLimit-Reset"] = "1780000000"
    response["headers"] = headers
    entry: dict[str, Any] = {"method": method, "path": path, "response": response}
    if params:
        entry["params"] = {key: str(value) for key, value in sorted(params.items())}
    return entry


class SessionBuilder:
    """Collects recorded entries for one profile session."""

    def __init__(self, profile_id: str, username: str, description: str) -> None:
        self.profile_id = profile_id
        self.username = username
        self.description = description
        self.entries: list[dict[str, Any]] = []

    def _path(self, path: str) -> str:
        return path.format(username=self.username)

    def add(
        self, method: str, path: str, params: dict[str, str] | None = None, **response: Any
    ) -> None:
        self.entries.append(_entry(method, self._path(path), params, **response))

    # --- individual endpoints ----------------------------------------------

    def user(self, payload: dict[str, Any]) -> None:
        self.add("GET", "/users/{username}", body=payload)

    def repositories(self, payloads: list[dict[str, Any]], *, per_page: int = 100) -> None:
        params = {"per_page": str(per_page), "page": "1"}
        link = None
        if len(payloads) > per_page:
            link = _link(f"/users/{self.username}/repos?page=2&per_page={per_page}")
        self.add("GET", "/users/{username}/repos", params, body=payloads[:per_page], link_next=link)
        if len(payloads) > per_page:
            self.add(
                "GET",
                "/users/{username}/repos",
                {"per_page": str(per_page), "page": "2"},
                body=payloads[per_page:],
            )

    def calendar(self, payload: dict[str, Any], restricted: int | None = None) -> None:
        collection: dict[str, Any] = {"contributionCalendar": payload}
        if restricted is not None:
            collection["restrictedContributionsCount"] = restricted
        self.add(
            "POST", "/graphql", body={"data": {"user": {"contributionsCollection": collection}}}
        )

    def followers(self, payloads: list[dict[str, Any]]) -> None:
        self.add(
            "GET", "/users/{username}/followers", {"per_page": "100", "page": "1"}, body=payloads
        )

    def following(self, payloads: list[dict[str, Any]]) -> None:
        self.add(
            "GET", "/users/{username}/following", {"per_page": "100", "page": "1"}, body=payloads
        )

    def search_pull_requests(self, items: list[dict[str, Any]]) -> None:
        self.add(
            "GET",
            "/search/issues",
            {"q": f"author:{self.username} type:pr", "per_page": "100", "page": "1"},
            body={"total_count": len(items), "incomplete_results": False, "items": items},
        )

    def search_issues(self, items: list[dict[str, Any]]) -> None:
        self.add(
            "GET",
            "/search/issues",
            {"q": f"author:{self.username} type:issue", "per_page": "100", "page": "1"},
            body={"total_count": len(items), "incomplete_results": False, "items": items},
        )

    def languages(self, owner: str, repo: str, payload: dict[str, int]) -> None:
        self.add("GET", f"/repos/{owner}/{repo}/languages", body=payload)

    def readme(self, owner: str, repo: str, payload: dict[str, Any] | None) -> None:
        if payload is None:
            self.add(
                "GET", f"/repos/{owner}/{repo}/readme", status=404, body={"message": "Not Found"}
            )
        else:
            self.add("GET", f"/repos/{owner}/{repo}/readme", body=payload)

    def commits(
        self,
        owner: str,
        repo: str,
        payloads: list[dict[str, Any]],
        *,
        author: str,
        per_page: int = 100,
    ) -> None:
        self.add(
            "GET",
            f"/repos/{owner}/{repo}/commits",
            {"author": author, "per_page": str(per_page), "page": "1"},
            body=payloads,
        )

    def pull_requests(
        self,
        owner: str,
        repo: str,
        payloads: list[dict[str, Any]],
        *,
        per_page: int = 100,
    ) -> None:
        self.add(
            "GET",
            f"/repos/{owner}/{repo}/pulls",
            {"state": "all", "per_page": str(per_page), "page": "1"},
            body=payloads,
        )

    def issues(
        self,
        owner: str,
        repo: str,
        payloads: list[dict[str, Any]],
        *,
        per_page: int = 100,
    ) -> None:
        self.add(
            "GET",
            f"/repos/{owner}/{repo}/issues",
            {"state": "all", "per_page": str(per_page), "page": "1"},
            body=payloads,
        )

    def stargazers(
        self,
        owner: str,
        repo: str,
        payloads: list[dict[str, Any]],
        *,
        per_page: int = 100,
    ) -> None:
        params = {"per_page": str(per_page), "page": "1"}
        link = None
        if len(payloads) > per_page:
            link = _link(f"/repos/{owner}/{repo}/stargazers?page=2&per_page={per_page}")
        self.add(
            "GET",
            f"/repos/{owner}/{repo}/stargazers",
            params,
            body=payloads[:per_page],
            link_next=link,
        )
        if len(payloads) > per_page:
            self.add(
                "GET",
                f"/repos/{owner}/{repo}/stargazers",
                {"per_page": str(per_page), "page": "2"},
                body=payloads[per_page:],
            )

    def build(self) -> dict[str, Any]:
        return {
            "version": CORPUS_VERSION,
            "profile": {
                "id": self.profile_id,
                "username": self.username,
                "description": self.description,
                "now": NOW,
            },
            "requests": self.entries,
        }


# --- profiles ----------------------------------------------------------------


def _active_developer() -> dict[str, Any]:
    username = "jane-doe"
    builder = SessionBuilder("active-developer", username, "A healthy, active developer profile.")
    builder.user(
        _user_payload(
            username,
            name="Jane Doe",
            bio="Building developer tools in the open.",
            company="Acme",
            blog="https://jane.dev",
            location="Berlin",
            email="jane@example.org",
            hireable=True,
            twitter_username="jane",
            public_repos=3,
            followers=320,
            following=48,
            created_at="2015-03-10T00:00:00Z",
        )
    )
    builder.repositories(
        [
            _repo_payload(
                username,
                "toolkit",
                stars=150,
                description="A CLI toolkit for developers",
                topics=["python", "cli", "developer-tools"],
                license_key="MIT",
                homepage="https://jane.dev/toolkit",
                language="Python",
                created_at="2016-05-01T00:00:00Z",
                pushed_at="2025-12-10T00:00:00Z",
            ),
            _repo_payload(
                username,
                "jane-doe",
                stars=5,
                description="My GitHub profile",
                topics=["profile"],
                language="Markdown",
                created_at="2020-01-01T00:00:00Z",
                pushed_at="2025-12-01T00:00:00Z",
            ),
            _repo_payload(
                username,
                "old-experiments",
                stars=1,
                fork=True,
                description="",
                language="JavaScript",
                created_at="2017-08-01T00:00:00Z",
                pushed_at="2019-06-01T00:00:00Z",
            ),
        ]
    )
    builder.calendar(
        _calendar(
            [
                ("2025-09-01", 2),
                ("2025-09-03", 4),
                ("2025-10-06", 3),
                ("2025-10-08", 5),
                ("2025-11-03", 4),
                ("2025-11-05", 2),
                ("2025-12-01", 6),
                ("2025-12-03", 3),
                ("2025-12-29", 2),
                ("2025-12-30", 3),
            ]
        )
    )
    builder.followers(
        [
            _follower_payload("follower-a"),
            _follower_payload("follower-b"),
            _follower_payload("follower-c"),
        ]
    )
    builder.following([_follower_payload("mentor"), _follower_payload("hero")])
    builder.search_pull_requests(
        [
            _pr_search_item(
                username,
                "toolkit",
                12,
                "Add CLI options",
                state="closed",
                merged=True,
                created_at="2025-11-05T09:00:00Z",
                closed_at="2025-11-10T09:00:00Z",
                merged_at="2025-11-10T09:00:00Z",
                comments=3,
                review_comments=2,
            ),
            _pr_search_item(
                username,
                "toolkit",
                14,
                "Fix parser crash",
                state="open",
                created_at="2025-12-20T09:00:00Z",
            ),
        ]
    )
    builder.search_issues(
        [
            _issue_payload(
                username,
                "toolkit",
                11,
                "Bug in parser",
                state="closed",
                created_at="2025-08-20T09:00:00Z",
                closed_at="2025-09-01T09:00:00Z",
                comments=2,
            ),
            _issue_payload(
                username,
                "toolkit",
                13,
                "Feature request",
                state="open",
                created_at="2025-12-01T09:00:00Z",
                comments=1,
            ),
        ]
    )
    builder.languages(username, "toolkit", {"Python": 5000, "JavaScript": 3000})
    builder.readme(
        username,
        "toolkit",
        _readme_payload(
            username,
            "toolkit",
            (
                "# Toolkit\n\nA CLI toolkit for developers.\n\n"
                "## Install\n\n```\npip install toolkit\n```\n"
            ),
        ),
    )
    builder.commits(
        username,
        "toolkit",
        [
            _commit_payload(
                username,
                "Jane Doe",
                "jane@example.org",
                "a" * 40,
                date="2025-10-01T10:00:00Z",
                message="feat: add CLI options",
            ),
            _commit_payload(
                username,
                "Jane Doe",
                "jane@example.org",
                "b" * 40,
                date="2025-11-01T11:00:00Z",
                message="fix: improve docs",
            ),
            _commit_payload(
                username,
                "Jane Doe",
                "jane@example.org",
                "c" * 40,
                date="2025-12-10T09:00:00Z",
                message="fix: parser crash",
            ),
        ],
        author=username,
    )
    builder.pull_requests(
        username,
        "toolkit",
        [
            _pr_payload(
                username,
                "toolkit",
                12,
                "Add CLI options",
                state="closed",
                merged=True,
                created_at="2025-11-05T09:00:00Z",
                closed_at="2025-11-10T09:00:00Z",
                merged_at="2025-11-10T09:00:00Z",
                comments=3,
                review_comments=2,
            )
        ],
    )
    builder.issues(
        username,
        "toolkit",
        [
            _issue_payload(
                username,
                "toolkit",
                13,
                "Feature request",
                state="open",
                created_at="2025-12-01T09:00:00Z",
                comments=1,
            )
        ],
    )
    builder.languages(username, "jane-doe", {"Markdown": 500})
    builder.readme(
        username,
        "jane-doe",
        _readme_payload(
            username,
            "jane-doe",
            (
                "# Hi, I'm Jane Doe\n\nI build developer tools in the open. "
                "Contact me at jane@example.org.\n\njane-doe\n"
            ),
        ),
    )
    builder.commits(
        username,
        "jane-doe",
        [
            _commit_payload(
                username,
                "Jane Doe",
                "jane@example.org",
                "d" * 40,
                date="2025-12-01T09:00:00Z",
                message="chore: refresh profile",
            )
        ],
        author=username,
    )
    builder.pull_requests(username, "jane-doe", [])
    builder.issues(username, "jane-doe", [])
    builder.languages(username, "old-experiments", {"JavaScript": 1000})
    builder.readme(username, "old-experiments", None)
    builder.commits(username, "old-experiments", [], author=username)
    builder.pull_requests(username, "old-experiments", [])
    builder.issues(username, "old-experiments", [])
    builder.stargazers(
        username,
        "toolkit",
        [
            _stargazer_payload("follower-a", "2025-10-01T00:00:00Z"),
            _stargazer_payload("follower-b", "2025-11-01T00:00:00Z"),
        ],
    )
    return builder.build()


def _minimal_profile() -> dict[str, Any]:
    username = "ghost-user"
    builder = SessionBuilder("minimal-profile", username, "A profile with no public activity.")
    builder.user(
        _user_payload(
            username, created_at="2024-01-01T00:00:00Z", updated_at="2025-12-01T00:00:00Z"
        )
    )
    builder.repositories([])
    builder.calendar(_calendar([]))
    builder.followers([])
    builder.following([])
    builder.search_pull_requests([])
    builder.search_issues([])
    return builder.build()


def _newcomer() -> dict[str, Any]:
    username = "new-dev"
    builder = SessionBuilder("newcomer", username, "A brand-new account just getting started.")
    builder.user(
        _user_payload(
            username,
            name="New Dev",
            bio="Learning to code.",
            public_repos=1,
            followers=1,
            following=2,
            created_at="2025-08-15T00:00:00Z",
        )
    )
    builder.repositories(
        [
            _repo_payload(
                username,
                "first-project",
                stars=3,
                description="My first project",
                topics=["learning"],
                language="Python",
                created_at="2025-09-01T00:00:00Z",
                pushed_at="2025-12-20T00:00:00Z",
            )
        ]
    )
    builder.calendar(_calendar([("2025-10-06", 2), ("2025-11-03", 1), ("2025-12-01", 3)]))
    builder.followers([_follower_payload("friend-one")])
    builder.following([_follower_payload("mentor"), _follower_payload("hero")])
    builder.search_pull_requests([])
    builder.search_issues([])
    builder.languages(username, "first-project", {"Python": 5000})
    builder.readme(
        username,
        "first-project",
        _readme_payload(username, "first-project", "# First Project\n\nMy very first project.\n"),
    )
    builder.commits(
        username,
        "first-project",
        [
            _commit_payload(
                username,
                "New Dev",
                "new@example.org",
                "e" * 40,
                date="2025-11-01T09:00:00Z",
                message="feat: initial commit",
            ),
            _commit_payload(
                username,
                "New Dev",
                "new@example.org",
                "f" * 40,
                date="2025-12-20T09:00:00Z",
                message="fix: readme",
            ),
        ],
        author=username,
    )
    builder.pull_requests(username, "first-project", [])
    builder.issues(username, "first-project", [])
    builder.stargazers(
        username, "first-project", [_stargazer_payload("friend-one", "2025-12-01T00:00:00Z")]
    )
    return builder.build()


def _popular_maintainer() -> dict[str, Any]:
    username = "ada-dev"
    builder = SessionBuilder(
        "popular-maintainer", username, "A widely-followed maintainer of a big project."
    )
    builder.user(
        _user_payload(
            username,
            name="Ada Dev",
            bio="Maintainer of forge.",
            company="Forgeworks",
            blog="https://ada.dev",
            location="London",
            email="ada@example.org",
            hireable=False,
            twitter_username="ada",
            public_repos=4,
            followers=890,
            following=12,
            created_at="2010-01-01T00:00:00Z",
        )
    )
    builder.repositories(
        [
            _repo_payload(
                username,
                "forge",
                stars=1240,
                description="A build toolchain",
                topics=["build", "toolchain"],
                license_key="Apache-2.0",
                homepage="https://forge.example",
                language="Rust",
                created_at="2012-03-01T00:00:00Z",
                pushed_at="2025-12-15T00:00:00Z",
            ),
            _repo_payload(
                username,
                "forge-docs",
                stars=310,
                description="Documentation for forge",
                topics=["docs"],
                license_key="Apache-2.0",
                language="Markdown",
                created_at="2016-07-01T00:00:00Z",
                pushed_at="2025-12-10T00:00:00Z",
            ),
            _repo_payload(
                username,
                "ada-dev",
                stars=12,
                description="My profile",
                language="Markdown",
                created_at="2019-01-01T00:00:00Z",
                pushed_at="2025-12-05T00:00:00Z",
            ),
            _repo_payload(
                username,
                "sidecar",
                stars=5,
                fork=True,
                description="",
                language="Go",
                created_at="2020-06-01T00:00:00Z",
                pushed_at="2023-01-01T00:00:00Z",
            ),
        ]
    )
    builder.calendar(
        _calendar(
            [
                ("2025-09-01", 8),
                ("2025-09-02", 12),
                ("2025-09-03", 7),
                ("2025-10-01", 10),
                ("2025-10-02", 9),
                ("2025-10-03", 11),
                ("2025-11-03", 14),
                ("2025-11-04", 6),
                ("2025-11-05", 13),
                ("2025-12-01", 9),
                ("2025-12-02", 10),
                ("2025-12-03", 8),
                ("2025-12-29", 5),
                ("2025-12-30", 7),
            ]
        )
    )
    builder.followers([_follower_payload(f"fan-{index}") for index in range(3)])
    builder.following([_follower_payload("colleague-a"), _follower_payload("colleague-b")])
    builder.search_pull_requests(
        [
            _pr_search_item(
                username,
                "forge",
                201,
                "Add incremental builds",
                state="closed",
                merged=True,
                created_at="2025-09-02T09:00:00Z",
                closed_at="2025-09-08T09:00:00Z",
                merged_at="2025-09-08T09:00:00Z",
                comments=5,
                review_comments=3,
            ),
            _pr_search_item(
                username,
                "forge",
                205,
                "Improve caching",
                state="closed",
                merged=True,
                created_at="2025-10-05T09:00:00Z",
                closed_at="2025-10-12T09:00:00Z",
                merged_at="2025-10-12T09:00:00Z",
                comments=2,
                review_comments=4,
            ),
            _pr_search_item(
                username,
                "forge",
                210,
                "Refactor scheduler",
                state="closed",
                merged=False,
                created_at="2025-11-01T09:00:00Z",
                closed_at="2025-11-15T09:00:00Z",
            ),
            _pr_search_item(
                username,
                "forge",
                214,
                "Add plugin API",
                state="open",
                created_at="2025-12-20T09:00:00Z",
                comments=1,
            ),
        ]
    )
    builder.search_issues(
        [
            _issue_payload(
                username,
                "forge",
                202,
                "Build cache is stale",
                state="closed",
                created_at="2025-09-10T09:00:00Z",
                closed_at="2025-09-20T09:00:00Z",
                comments=4,
            ),
            _issue_payload(
                username,
                "forge",
                206,
                "Docs are out of date",
                state="closed",
                created_at="2025-10-15T09:00:00Z",
                closed_at="2025-10-25T09:00:00Z",
                comments=2,
            ),
            _issue_payload(
                username,
                "forge",
                213,
                "Plugin loading is slow",
                state="open",
                created_at="2025-12-10T09:00:00Z",
                comments=3,
            ),
        ]
    )
    builder.languages(username, "forge", {"Rust": 120000, "Shell": 8000})
    builder.readme(
        username,
        "forge",
        _readme_payload(
            username,
            "forge",
            "# Forge\n\nA build toolchain.\n\n## Usage\n\n```\nforge build\n```\n",
        ),
    )
    builder.commits(
        username,
        "forge",
        [
            _commit_payload(
                username,
                "Ada Dev",
                "ada@example.org",
                "g" * 40,
                date="2025-10-01T09:00:00Z",
                message="feat: incremental builds",
            ),
            _commit_payload(
                username,
                "Ada Dev",
                "ada@example.org",
                "h" * 40,
                date="2025-11-01T09:00:00Z",
                message="fix: cache invalidation",
            ),
            _commit_payload(
                username,
                "Ada Dev",
                "ada@example.org",
                "i" * 40,
                date="2025-12-15T09:00:00Z",
                message="feat: plugin API",
            ),
        ],
        author=username,
    )
    builder.pull_requests(
        username,
        "forge",
        [
            _pr_payload(
                username,
                "forge",
                205,
                "Improve caching",
                state="closed",
                merged=True,
                created_at="2025-10-05T09:00:00Z",
                closed_at="2025-10-12T09:00:00Z",
                merged_at="2025-10-12T09:00:00Z",
                comments=2,
                review_comments=4,
            ),
            _pr_payload(
                username,
                "forge",
                210,
                "Refactor scheduler",
                state="closed",
                merged=False,
                created_at="2025-11-01T09:00:00Z",
                closed_at="2025-11-15T09:00:00Z",
            ),
            _pr_payload(
                username,
                "forge",
                214,
                "Add plugin API",
                state="open",
                created_at="2025-12-20T09:00:00Z",
                comments=1,
            ),
        ],
    )
    builder.issues(
        username,
        "forge",
        [
            _issue_payload(
                username,
                "forge",
                202,
                "Build cache is stale",
                state="closed",
                created_at="2025-09-10T09:00:00Z",
                closed_at="2025-09-20T09:00:00Z",
                comments=4,
            ),
            _issue_payload(
                username,
                "forge",
                213,
                "Plugin loading is slow",
                state="open",
                created_at="2025-12-10T09:00:00Z",
                comments=3,
            ),
        ],
    )
    builder.languages(username, "forge-docs", {"Markdown": 40000})
    builder.readme(
        username,
        "forge-docs",
        _readme_payload(username, "forge-docs", "# Forge Docs\n\nThe documentation for forge.\n"),
    )
    builder.commits(
        username,
        "forge-docs",
        [
            _commit_payload(
                username,
                "Ada Dev",
                "ada@example.org",
                "j" * 40,
                date="2025-12-10T09:00:00Z",
                message="docs: update quickstart",
            ),
            _commit_payload(
                username,
                "Ada Dev",
                "ada@example.org",
                "k" * 40,
                date="2025-11-01T09:00:00Z",
                message="docs: add examples",
            ),
        ],
        author=username,
    )
    builder.pull_requests(username, "forge-docs", [])
    builder.issues(
        username,
        "forge-docs",
        [
            _issue_payload(
                username,
                "forge-docs",
                55,
                "Typo in quickstart",
                state="closed",
                created_at="2025-10-01T09:00:00Z",
                closed_at="2025-10-05T09:00:00Z",
            )
        ],
    )
    builder.languages(username, "ada-dev", {"Markdown": 900})
    builder.readme(
        username,
        "ada-dev",
        _readme_payload(
            username,
            "ada-dev",
            "# Ada Dev\n\nMaintainer of forge. Find me at ada.dev.\n\nada-dev\n",
        ),
    )
    builder.commits(username, "ada-dev", [], author=username)
    builder.pull_requests(username, "ada-dev", [])
    builder.issues(username, "ada-dev", [])
    builder.languages(username, "sidecar", {"Go": 2000})
    builder.readme(username, "sidecar", None)
    builder.commits(username, "sidecar", [], author=username)
    builder.pull_requests(username, "sidecar", [])
    builder.issues(username, "sidecar", [])
    builder.stargazers(
        username,
        "forge",
        [
            _stargazer_payload("fan-1", "2025-12-01T00:00:00Z"),
            _stargazer_payload("fan-2", "2025-12-20T00:00:00Z"),
        ],
    )
    return builder.build()


def _archived_heavy() -> dict[str, Any]:
    username = "historian"
    builder = SessionBuilder(
        "archived-heavy", username, "A portfolio dominated by archived repositories."
    )
    builder.user(
        _user_payload(
            username,
            name="Historian",
            bio="Preserving old code.",
            public_repos=3,
            followers=3,
            following=20,
            created_at="2012-06-01T00:00:00Z",
        )
    )
    builder.repositories(
        [
            _repo_payload(
                username,
                "legacy-app",
                stars=40,
                archived=True,
                description="A legacy monolith",
                language="Java",
                created_at="2013-02-01T00:00:00Z",
                pushed_at="2019-06-01T00:00:00Z",
            ),
            _repo_payload(
                username,
                "deprecated-lib",
                stars=15,
                archived=True,
                description=None,
                language="C++",
                created_at="2014-09-01T00:00:00Z",
                pushed_at="2018-03-01T00:00:00Z",
            ),
            _repo_payload(
                username,
                "active-tool",
                stars=3,
                description="A small maintenance tool",
                language="Python",
                created_at="2020-01-01T00:00:00Z",
                pushed_at="2025-06-01T00:00:00Z",
            ),
        ]
    )
    builder.calendar(_calendar([("2025-03-03", 1), ("2025-06-02", 2), ("2025-11-03", 1)]))
    builder.followers(
        [
            _follower_payload("friend-a"),
            _follower_payload("friend-b"),
            _follower_payload("friend-c"),
        ]
    )
    builder.following(
        [
            _follower_payload("colleague-a"),
            _follower_payload("colleague-b"),
            _follower_payload("colleague-c"),
        ]
    )
    builder.search_pull_requests(
        [
            _pr_search_item(
                username,
                "legacy-app",
                42,
                "Fix login flow",
                state="closed",
                merged=True,
                created_at="2019-04-01T09:00:00Z",
                closed_at="2019-04-10T09:00:00Z",
                merged_at="2019-04-10T09:00:00Z",
                comments=2,
                review_comments=1,
            )
        ]
    )
    builder.search_issues(
        [
            _issue_payload(
                username,
                "legacy-app",
                41,
                "Login is broken",
                state="closed",
                created_at="2018-11-01T09:00:00Z",
                closed_at="2018-11-20T09:00:00Z",
                comments=3,
            )
        ]
    )
    builder.languages(username, "legacy-app", {"Java": 40000})
    builder.readme(username, "legacy-app", None)
    builder.commits(
        username,
        "legacy-app",
        [
            _commit_payload(
                username,
                "Historian",
                "historian@example.org",
                "l" * 40,
                date="2019-06-01T09:00:00Z",
                message="chore: archive repository",
            )
        ],
        author=username,
    )
    builder.pull_requests(
        username,
        "legacy-app",
        [
            _pr_payload(
                username,
                "legacy-app",
                42,
                "Fix login flow",
                state="closed",
                merged=True,
                created_at="2019-04-01T09:00:00Z",
                closed_at="2019-04-10T09:00:00Z",
                merged_at="2019-04-10T09:00:00Z",
                comments=2,
                review_comments=1,
            )
        ],
    )
    builder.issues(username, "legacy-app", [])
    builder.languages(username, "deprecated-lib", {"C++": 20000})
    builder.readme(username, "deprecated-lib", None)
    builder.commits(username, "deprecated-lib", [], author=username)
    builder.pull_requests(username, "deprecated-lib", [])
    builder.issues(username, "deprecated-lib", [])
    builder.languages(username, "active-tool", {"Python": 3000})
    builder.readme(
        username,
        "active-tool",
        _readme_payload(username, "active-tool", "# Active Tool\n\nA small maintenance tool.\n"),
    )
    builder.commits(
        username,
        "active-tool",
        [
            _commit_payload(
                username,
                "Historian",
                "historian@example.org",
                "m" * 40,
                date="2025-06-01T09:00:00Z",
                message="fix: handle edge case",
            )
        ],
        author=username,
    )
    builder.pull_requests(username, "active-tool", [])
    builder.issues(username, "active-tool", [])
    builder.stargazers(
        username, "legacy-app", [_stargazer_payload("friend-a", "2019-01-01T00:00:00Z")]
    )
    return builder.build()


def _hidden_activity() -> dict[str, Any]:
    username = "private-dev"
    builder = SessionBuilder(
        "hidden-activity", username, "A profile with private activity and placeholder content."
    )
    builder.user(
        _user_payload(
            username,
            name="Private Dev",
            public_repos=2,
            followers=1,
            following=3,
            created_at="2016-05-20T00:00:00Z",
        )
    )
    builder.repositories(
        [
            _repo_payload(
                username,
                "private-dev",
                stars=0,
                description="Private development",
                language="Markdown",
                created_at="2020-03-01T00:00:00Z",
                pushed_at="2025-12-05T00:00:00Z",
            ),
            _repo_payload(
                username,
                "work-in-progress",
                stars=2,
                description="Coming soon",
                language="Python",
                created_at="2025-11-01T00:00:00Z",
                pushed_at="2025-11-20T00:00:00Z",
            ),
        ]
    )
    builder.calendar(
        _calendar(
            [("2025-10-06", 1), ("2025-12-01", 2), ("2025-12-29", 2)],
        ),
        restricted=120,
    )
    builder.followers([_follower_payload("silent-observer")])
    builder.following(
        [
            _follower_payload("colleague-a"),
            _follower_payload("colleague-b"),
            _follower_payload("colleague-c"),
        ]
    )
    builder.search_pull_requests([])
    builder.search_issues([])
    builder.languages(username, "private-dev", {"Markdown": 200})
    builder.readme(
        username,
        "private-dev",
        _readme_payload(
            username,
            "private-dev",
            (
                "This is a profile readme.\n\nWelcome to my GitHub profile.\n\n"
                "More content coming soon.\n"
            ),
        ),
    )
    builder.commits(username, "private-dev", [], author=username)
    builder.pull_requests(username, "private-dev", [])
    builder.issues(username, "private-dev", [])
    builder.languages(username, "work-in-progress", {"Python": 1500})
    builder.readme(username, "work-in-progress", None)
    builder.commits(
        username,
        "work-in-progress",
        [
            _commit_payload(
                username,
                "Private Dev",
                "private@example.org",
                "n" * 40,
                date="2025-11-20T09:00:00Z",
                message="wip: initial sketch",
            )
        ],
        author=username,
    )
    builder.pull_requests(username, "work-in-progress", [])
    builder.issues(username, "work-in-progress", [])
    builder.stargazers(
        username,
        "work-in-progress",
        [_stargazer_payload("silent-observer", "2025-12-01T00:00:00Z")],
    )
    return builder.build()


# --- error sessions -----------------------------------------------------------


def _user_not_found() -> dict[str, Any]:
    builder = SessionBuilder("user-not-found", "ghost", "A profile that does not exist on GitHub.")
    builder.add("GET", "/users/{username}", status=404, body={"message": "Not Found"})
    return builder.build()


def _rate_limit() -> dict[str, Any]:
    builder = SessionBuilder("rate-limit", "ghost", "A primary rate-limit (403) response.")
    builder.add(
        "GET",
        "/users/{username}",
        status=403,
        body={"message": "API rate limit exceeded"},
        rate_limit_remaining=0,
    )
    return builder.build()


def _malformed() -> dict[str, Any]:
    builder = SessionBuilder("malformed", "ghost", "A response with invalid JSON.")
    builder.add("GET", "/users/{username}", content="<html>this is not json</html>")
    return builder.build()


_FULL_PROFILES = [
    _active_developer,
    _minimal_profile,
    _newcomer,
    _popular_maintainer,
    _archived_heavy,
    _hidden_activity,
]
_ERROR_SESSIONS = [_user_not_found, _rate_limit, _malformed]


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def generate() -> list[Path]:
    written: list[Path] = []
    index: dict[str, Any] = {"version": CORPUS_VERSION, "profiles": []}
    for builder in _FULL_PROFILES:
        session = builder()
        directory = CORPUS_DIR / session["profile"]["id"]
        path = directory / "session.json"
        _write(path, session)
        written.append(path)
        index["profiles"].append(
            {
                "id": session["profile"]["id"],
                "username": session["profile"]["username"],
                "description": session["profile"]["description"],
                "requests": len(session["requests"]),
            }
        )
    for builder in _ERROR_SESSIONS:
        session = builder()
        directory = CORPUS_DIR / "errors" / session["profile"]["id"]
        path = directory / "session.json"
        _write(path, session)
        written.append(path)
        index["profiles"].append(
            {
                "id": f"errors/{session['profile']['id']}",
                "username": session["profile"]["username"],
                "description": session["profile"]["description"],
                "requests": len(session["requests"]),
            }
        )
    manifest = CORPUS_DIR / "MANIFEST.json"
    _write(manifest, index)
    written.append(manifest)
    return written


if __name__ == "__main__":
    paths = generate()
    print(f"Generated {len(paths)} files under {CORPUS_DIR}.")
