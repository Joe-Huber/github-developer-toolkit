"""Raw GitHub ``Issue`` model.

Mirrors the issue objects returned by ``GET /repos/{owner}/{repo}/issues``
and ``GET /issues``.
"""

from __future__ import annotations

from datetime import datetime

from ghdtk.models.raw._base import BaseRawModel
from ghdtk.models.raw.issue_shared import Label, Milestone
from ghdtk.models.raw.user import User


class Issue(BaseRawModel):
    """An issue as returned by the API."""

    id: int | None = None
    node_id: str | None = None
    url: str | None = None
    repository_url: str | None = None
    labels_url: str | None = None
    comments_url: str | None = None
    events_url: str | None = None
    html_url: str | None = None
    number: int | None = None
    state: str | None = None
    title: str | None = None
    body: str | None = None
    user: User | None = None
    labels: list[Label] | None = None
    assignee: User | None = None
    assignees: list[User] | None = None
    milestone: Milestone | None = None
    locked: bool | None = None
    active_lock_reason: str | None = None
    comments: int | None = None
    pull_request: dict[str, object] | None = None
    closed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    author_association: str | None = None
