"""Unit tests for Link-header pagination helpers (issue #18)."""

from __future__ import annotations

import httpx

from ghdtk.api.pagination import (
    has_next_page,
    next_page_url,
    next_params,
    parse_link_header,
)


def _response(*, link: str | None = None) -> httpx.Response:
    headers = {"Link": link} if link is not None else {}
    return httpx.Response(200, headers=headers)


def test_parse_link_header_full() -> None:
    link = (
        '<https://api.github.com/users/x/repos?page=2>; rel="next", '
        '<https://api.github.com/users/x/repos?page=3>; rel="last", '
        '<https://api.github.com/users/x/repos?page=1>; rel="prev"'
    )
    parsed = parse_link_header(link)
    assert parsed["next"] == "https://api.github.com/users/x/repos?page=2"
    assert parsed["last"] == "https://api.github.com/users/x/repos?page=3"
    assert parsed["prev"] == "https://api.github.com/users/x/repos?page=1"


def test_parse_link_header_none() -> None:
    assert parse_link_header(None) == {}


def test_parse_link_header_missing_rel_ignored() -> None:
    assert parse_link_header("<https://api.github.com/users/x/repos?page=2>") == {}


def test_next_page_url_present() -> None:
    response = _response(link='<https://api.github.com/users/x/repos?page=2>; rel="next"')
    assert next_page_url(response) == "https://api.github.com/users/x/repos?page=2"


def test_next_page_url_absent() -> None:
    assert (
        next_page_url(_response(link='<https://api.github.com/users/x/repos?page=1>; rel="last"'))
        is None
    )
    assert next_page_url(_response()) is None


def test_has_next_page() -> None:
    assert has_next_page(
        _response(link='<https://api.github.com/users/x/repos?page=2>; rel="next"')
    )
    assert not has_next_page(_response())


def test_next_params_increments_page() -> None:
    assert next_params(_response(), {"page": 2, "per_page": 100}) == {
        "page": 3,
        "per_page": 100,
    }


def test_next_params_defaults_to_page_one() -> None:
    assert next_params(_response(), {"per_page": 100}) == {"page": 2, "per_page": 100}
