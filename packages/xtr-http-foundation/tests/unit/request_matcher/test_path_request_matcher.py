"""The path of a request, held to a regular expression."""

from __future__ import annotations

import pytest
from xtr_http_message import ServerRequest

from xtr_http_foundation import PathRequestMatcher
from xtr_http_foundation.exception import InvalidArgumentError


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("regexp", "expected"),
    [
        ("/admin/.*", True),
        ("/admin", True),
        ("^/admin/.*$", True),
        ("/blog/.*", False),
    ],
)
async def test_it_matches_the_path(regexp: str, expected: bool) -> None:
    matcher = PathRequestMatcher(regexp)

    assert await matcher.matches(ServerRequest("GET", "/admin/foo")) is expected


@pytest.mark.anyio
async def test_it_does_not_read_a_placeholder_as_a_path_parameter() -> None:
    matcher = PathRequestMatcher("^/{_locale}/login$")

    assert await matcher.matches(ServerRequest("GET", "/en/login")) is False


@pytest.mark.anyio
async def test_it_matches_a_path_whose_characters_arrived_escaped() -> None:
    matcher = PathRequestMatcher("^/admin/fo o*$")

    assert await matcher.matches(ServerRequest("GET", "/admin/fo%20o")) is True


@pytest.mark.anyio
@pytest.mark.parametrize("regexp", ["^.*$", "^/.*$", "^/admin/.*$"])
async def test_it_matches_across_a_control_character_that_arrived_escaped(regexp: str) -> None:
    matcher = PathRequestMatcher(regexp)

    assert await matcher.matches(ServerRequest("GET", "/admin/fo%0Ao")) is True


@pytest.mark.anyio
async def test_it_matches_the_path_below_where_the_application_is_mounted() -> None:
    matcher = PathRequestMatcher("^/admin/foo$")
    request = ServerRequest("GET", "/shop/admin/foo", server_params={"root_path": "/shop"})

    assert await matcher.matches(request) is True


@pytest.mark.anyio
async def test_it_matches_the_whole_path_where_the_application_is_mounted_at_the_root() -> None:
    matcher = PathRequestMatcher("^/admin/foo$")
    request = ServerRequest("GET", "/admin/foo", server_params={"root_path": ""})

    assert await matcher.matches(request) is True


def test_it_refuses_an_expression_that_does_not_read_as_one() -> None:
    with pytest.raises(InvalidArgumentError, match=r'"\(unclosed" is not a valid'):
        _ = PathRequestMatcher("(unclosed")
