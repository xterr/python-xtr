"""Headers a request has to carry, whatever they say."""

from __future__ import annotations

import pytest
from xtr_http_message import ServerRequest

from xtr_http_foundation import HeaderRequestMatcher

_FOR_SEVERAL: list[tuple[dict[str, str], bool]] = [
    # A header beyond the ones asked for
    ({"X-Foo": "foo", "bar": "bar", "baz": "baz"}, True),
    # Exactly the ones asked for
    ({"X-Foo": "foo", "bar": "bar"}, True),
    # Written in another case
    ({"x-foo": "foo", "BAR": "bar"}, True),
    # Only one of the two
    ({"bar": "bar", "baz": "baz"}, False),
    # Only the other one
    ({"X-foo": "foo"}, False),
    # The name sent as a value rather than as a name
    ({"0": "X-foo"}, False),
    # No headers at all
    ({}, False),
]

_FOR_ONE: list[tuple[dict[str, str], bool]] = [
    # A header beyond the one asked for
    ({"X-Foo": "foo", "bar": "bar"}, True),
    # Exactly the one asked for
    ({"X-foo": "foo"}, True),
    # Written in another case
    ({"x-foo": "foo"}, True),
    # The name sent as a value rather than as a name
    ({"0": "X-foo"}, False),
    # No headers at all
    ({}, False),
]


def _carrying(headers: dict[str, str]) -> ServerRequest:
    return ServerRequest("GET", "https://example.com", headers)


@pytest.mark.anyio
@pytest.mark.parametrize(("headers", "matches"), _FOR_SEVERAL)
async def test_it_matches_a_list_of_names(headers: dict[str, str], matches: bool) -> None:
    matcher = HeaderRequestMatcher(["x-foo", "bar"])

    assert await matcher.matches(_carrying(headers)) is matches


@pytest.mark.anyio
@pytest.mark.parametrize(("headers", "matches"), _FOR_SEVERAL)
async def test_it_matches_names_separated_by_commas(headers: dict[str, str], matches: bool) -> None:
    matcher = HeaderRequestMatcher("x-foo, bar")

    assert await matcher.matches(_carrying(headers)) is matches


@pytest.mark.anyio
@pytest.mark.parametrize(("headers", "matches"), _FOR_ONE)
async def test_it_matches_one_name(headers: dict[str, str], matches: bool) -> None:
    matcher = HeaderRequestMatcher("x-foo")

    assert await matcher.matches(_carrying(headers)) is matches


@pytest.mark.anyio
async def test_it_claims_every_request_when_it_names_no_header() -> None:
    matcher = HeaderRequestMatcher([])

    assert await matcher.matches(_carrying({})) is True
