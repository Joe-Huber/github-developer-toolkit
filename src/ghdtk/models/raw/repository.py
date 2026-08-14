"""Raw GitHub ``Repository`` model.

Mirrors the REST API repository object returned by ``GET /repos/{owner}/{repo}``
and by the repository listing endpoints.
"""

from __future__ import annotations

from datetime import datetime

from ghdtk.models.raw._base import BaseRawModel
from ghdtk.models.raw.user import User


class License(BaseRawModel):
    """License metadata attached to a repository."""

    key: str | None = None
    name: str | None = None
    spdx_id: str | None = None
    url: str | None = None
    node_id: str | None = None


class Repository(BaseRawModel):
    """A GitHub repository as returned by the API."""

    id: int | None = None
    node_id: str | None = None
    name: str | None = None
    full_name: str | None = None
    private: bool | None = None
    owner: User | None = None
    html_url: str | None = None
    description: str | None = None
    fork: bool | None = None
    url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    pushed_at: datetime | None = None
    homepage: str | None = None
    size: int | None = None
    stargazers_count: int | None = None
    watchers_count: int | None = None
    language: str | None = None
    has_issues: bool | None = None
    has_projects: bool | None = None
    has_downloads: bool | None = None
    has_wiki: bool | None = None
    has_pages: bool | None = None
    has_discussions: bool | None = None
    forks_count: int | None = None
    mirror_url: str | None = None
    archived: bool | None = None
    disabled: bool | None = None
    open_issues_count: int | None = None
    license: License | None = None
    allow_forking: bool | None = None
    is_template: bool | None = None
    web_commit_signoff_required: bool | None = None
    topics: list[str] | None = None
    visibility: str | None = None
    forks: int | None = None
    open_issues: int | None = None
    watchers: int | None = None
    default_branch: str | None = None
    default_branch_protected: bool | None = None
    permissions: dict[str, bool] | None = None
