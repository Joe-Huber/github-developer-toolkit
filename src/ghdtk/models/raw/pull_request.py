"""Raw GitHub ``PullRequest`` model.

Mirrors the pull request objects returned by ``GET /repos/{owner}/{repo}/pulls``.
"""

from __future__ import annotations

from datetime import datetime

from ghdtk.models.raw._base import BaseRawModel
from ghdtk.models.raw.issue_shared import Label
from ghdtk.models.raw.repository import Repository
from ghdtk.models.raw.user import User


class PullRequestRef(BaseRawModel):
    """The ``head`` or ``base`` ref of a pull request."""

    label: str | None = None
    ref: str | None = None
    sha: str | None = None
    user: User | None = None
    repo: Repository | None = None


class PullRequest(BaseRawModel):
    """A pull request as returned by the API."""

    url: str | None = None
    id: int | None = None
    node_id: str | None = None
    html_url: str | None = None
    repository_url: str | None = None
    diff_url: str | None = None
    patch_url: str | None = None
    issue_url: str | None = None
    number: int | None = None
    state: str | None = None
    locked: bool | None = None
    title: str | None = None
    user: User | None = None
    body: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    closed_at: datetime | None = None
    merged_at: datetime | None = None
    merge_commit_sha: str | None = None
    assignee: User | None = None
    assignees: list[User] | None = None
    requested_reviewers: list[User] | None = None
    labels: list[Label] | None = None
    draft: bool | None = None
    commits_url: str | None = None
    review_comments_url: str | None = None
    review_comment_url: str | None = None
    comments_url: str | None = None
    statuses_url: str | None = None
    head: PullRequestRef | None = None
    base: PullRequestRef | None = None
    author_association: str | None = None
    auto_merge: dict[str, object] | None = None
    active_lock_reason: str | None = None
    merged: bool | None = None
    mergeable: bool | None = None
    rebaseable: bool | None = None
    mergeable_state: str | None = None
    merged_by: User | None = None
    comments: int | None = None
    review_comments: int | None = None
    maintainer_can_modify: bool | None = None
    commits: int | None = None
    additions: int | None = None
    deletions: int | None = None
    changed_files: int | None = None
