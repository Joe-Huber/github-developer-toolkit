"""Raw GitHub ``Stargazer`` model.

Mirrors the user objects returned by ``GET /repos/{owner}/{repo}/stargazers``.
``starred_at`` is populated when the timeline-preview accept header is used.
"""

from __future__ import annotations

from datetime import datetime

from ghdtk.models.raw._base import BaseRawModel


class Stargazer(BaseRawModel):
    """A user who starred a repository."""

    login: str | None = None
    id: int | None = None
    node_id: str | None = None
    avatar_url: str | None = None
    html_url: str | None = None
    type: str | None = None
    site_admin: bool | None = None
    starred_at: datetime | None = None
