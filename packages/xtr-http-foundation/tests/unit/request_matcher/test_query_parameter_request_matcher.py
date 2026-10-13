"""Query parameters a request has to open with, whatever they say."""

from __future__ import annotations

import pytest
from xtr_http_message import ServerRequest

from xtr_http_foundation import QueryParameterRequestMatcher

_FOR_SEVERAL: list[tuple[str, bool]] = [
    ("https://example.com?foo=&bar=", True),
    ("https://example.com?foo=foo1&bar=bar1", True),
    ("https://example.com?foo=foo1&bar=bar1&baz=baz1", True),
    ("https://example.com?foo=", False),
    ("https://example.com", False),
]

_FOR_ONE: list[tuple[str, bool]] = [
    ("https://example.com?foo=&bar=", True),
    ("https://example.com?foo=foo1", True),
    ("https://example.com?foo=", True),
    ("https://example.com?bar=bar1&baz=baz1", False),
    ("https://example.com", False),
]


@pytest.mark.anyio
@pytest.mark.parametrize(("uri", "matches"), _FOR_SEVERAL)
async def test_it_matches_a_list_of_names(uri: str, matches: bool) -> None:
    matcher = QueryParameterRequestMatcher(["foo", "bar"])

    assert await matcher.matches(ServerRequest("GET", uri)) is matches


@pytest.mark.anyio
@pytest.mark.parametrize(("uri", "matches"), _FOR_SEVERAL)
async def test_it_matches_names_separated_by_commas(uri: str, matches: bool) -> None:
    matcher = QueryParameterRequestMatcher("foo, bar")

    assert await matcher.matches(ServerRequest("GET", uri)) is matches


@pytest.mark.anyio
@pytest.mark.parametrize(("uri", "matches"), _FOR_ONE)
async def test_it_matches_one_name(uri: str, matches: bool) -> None:
    matcher = QueryParameterRequestMatcher("foo")

    assert await matcher.matches(ServerRequest("GET", uri)) is matches


@pytest.mark.anyio
async def test_it_matches_the_names_by_position() -> None:
    matcher = QueryParameterRequestMatcher(["foo", "bar"])

    assert await matcher.matches(ServerRequest("GET", "https://example.com?bar=1&foo=2")) is False


@pytest.mark.anyio
async def test_it_matches_a_name_written_in_another_case_only_as_it_arrived() -> None:
    matcher = QueryParameterRequestMatcher("FOO")

    assert await matcher.matches(ServerRequest("GET", "https://example.com?foo=1")) is True
    assert await matcher.matches(ServerRequest("GET", "https://example.com?FOO=1")) is False


@pytest.mark.anyio
async def test_it_claims_every_request_when_it_names_no_parameter() -> None:
    matcher = QueryParameterRequestMatcher([])

    assert await matcher.matches(ServerRequest("GET", "https://example.com")) is True
