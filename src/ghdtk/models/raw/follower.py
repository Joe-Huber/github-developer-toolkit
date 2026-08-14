"""Raw GitHub ``Follower`` model.

Mirrors the user objects returned by ``GET /users/{username}/followers``.
``followed_at`` is reserved for timeline-style payloads that include it.
"""

from __future__ import annotations

from datetime import datetime

from ghdtk.models.raw._base import BaseRawModel


class Follower(BaseRawModel):
    """A user that follows the analyzed profile."""

    login: str | None = None
    id: int | None = None
    node_id: str | None = None
    avatar_url: str | None = None
    html_url: str | None = None
    type: str | None = None
    site_admin: bool | None = None
    followed_at: datetime | None = None
