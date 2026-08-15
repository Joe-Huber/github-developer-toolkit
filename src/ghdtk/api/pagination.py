"""Pagination helpers for the GitHub API client.

GitHub paginates list and search endpoints with ``Link`` headers (``rel``
= ``next``/``last``/etc.). These helpers parse those headers so the client can
walk every page of a dataset (issue #18).
"""

from __future__ import annotations

import re
from typing import Any

import httpx

_LINK_PATTERN = re.compile(r'<(?P<url>[^>]+)>\s*;\s*rel="(?P<rel>[^"]+)"')


def parse_link_header(value: str | None) -> dict[str, str]:
    """Parse a ``Link`` header into a mapping of ``rel`` to URL."""
    if value is None:
        return {}
    links: dict[str, str] = {}
    for part in value.split(","):
        match = _LINK_PATTERN.search(part.strip())
        if match is not None:
            links[match.group("rel")] = match.group("url")
    return links


def next_page_url(response: httpx.Response) -> str | None:
    """Return the URL of the next page, or ``None`` on the last page."""
    return parse_link_header(response.headers.get("Link")).get("next")


def has_next_page(response: httpx.Response) -> bool:
    """Whether the response advertises a next page."""
    return next_page_url(response) is not None


def next_params(response: httpx.Response, params: dict[str, Any]) -> dict[str, Any]:
    """Build the ``page`` parameter for the next page (fallback when no Link)."""
    page = int(params.get("page", 1))
    next_params_value = dict(params)
    next_params_value["page"] = page + 1
    return next_params_value


__all__ = [
    "has_next_page",
    "next_page_url",
    "next_params",
    "parse_link_header",
]
