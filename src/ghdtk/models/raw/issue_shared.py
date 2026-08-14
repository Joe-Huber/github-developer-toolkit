"""Raw GitHub issue-related shared models.

``Label`` and ``Milestone`` are embedded in both issue and pull request
payloads, so they live in their own module to avoid import cycles.
"""

from __future__ import annotations

from datetime import datetime

from ghdtk.models.raw._base import BaseRawModel
from ghdtk.models.raw.user import User


class Label(BaseRawModel):
    """A label attached to an issue or pull request."""

    id: int | None = None
    node_id: str | None = None
    url: str | None = None
    name: str | None = None
    color: str | None = None
    default: bool | None = None
    description: str | None = None


class Milestone(BaseRawModel):
    """A milestone attached to an issue or pull request."""

    url: str | None = None
    html_url: str | None = None
    labels_url: str | None = None
    id: int | None = None
    node_id: str | None = None
    number: int | None = None
    state: str | None = None
    title: str | None = None
    description: str | None = None
    creator: User | None = None
    open_issues: int | None = None
    closed_issues: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    closed_at: datetime | None = None
    due_on: datetime | None = None
