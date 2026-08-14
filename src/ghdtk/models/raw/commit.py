"""Raw GitHub ``Commit`` model.

Mirrors the commit items returned by ``GET /repos/{owner}/{repo}/commits``
(including their nested ``commit`` detail).
"""

from __future__ import annotations

from datetime import datetime

from ghdtk.models.raw._base import BaseRawModel
from ghdtk.models.raw.user import User


class GitUser(BaseRawModel):
    """Author/committer identity embedded in a commit."""

    name: str | None = None
    email: str | None = None
    date: datetime | None = None


class Tree(BaseRawModel):
    """Git tree reference embedded in a commit."""

    sha: str | None = None
    url: str | None = None


class Verification(BaseRawModel):
    """Commit signature verification details."""

    verified: bool | None = None
    reason: str | None = None
    signature: str | None = None
    payload: str | None = None


class CommitDetail(BaseRawModel):
    """The ``commit`` object of a commit list item."""

    author: GitUser | None = None
    committer: GitUser | None = None
    message: str | None = None
    tree: Tree | None = None
    url: str | None = None
    comment_count: int | None = None
    verification: Verification | None = None


class CommitParent(BaseRawModel):
    """Parent commit reference."""

    sha: str | None = None
    url: str | None = None
    html_url: str | None = None


class Commit(BaseRawModel):
    """A commit as returned by the commits listing endpoint."""

    sha: str | None = None
    node_id: str | None = None
    commit: CommitDetail | None = None
    url: str | None = None
    html_url: str | None = None
    comments_url: str | None = None
    author: User | None = None
    committer: User | None = None
    parents: list[CommitParent] | None = None
