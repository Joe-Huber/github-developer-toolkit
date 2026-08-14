"""Raw GitHub ``User`` model.

Mirrors the REST API user object returned by ``GET /users/{username}``,
``GET /user``, and embedded in most other payloads.
"""

from __future__ import annotations

from datetime import datetime

from ghdtk.models.raw._base import BaseRawModel


class User(BaseRawModel):
    """A GitHub account as returned by the API."""

    login: str
    id: int | None = None
    node_id: str | None = None
    avatar_url: str | None = None
    gravatar_id: str | None = None
    url: str | None = None
    html_url: str | None = None
    followers_url: str | None = None
    following_url: str | None = None
    gists_url: str | None = None
    starred_url: str | None = None
    subscriptions_url: str | None = None
    organizations_url: str | None = None
    repos_url: str | None = None
    events_url: str | None = None
    received_events_url: str | None = None
    type: str | None = None
    site_admin: bool | None = None
    name: str | None = None
    company: str | None = None
    blog: str | None = None
    location: str | None = None
    email: str | None = None
    hireable: bool | None = None
    bio: str | None = None
    twitter_username: str | None = None
    public_repos: int | None = None
    public_gists: int | None = None
    followers: int | None = None
    following: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
