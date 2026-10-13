"""The port a request was asked of."""

from __future__ import annotations

import pytest
from xtr_http_message import ServerRequest

from xtr_http_foundation import PortRequestMatcher


@pytest.mark.anyio
@pytest.mark.parametrize(("port", "expected"), [(8000, True), (9000, False)])
async def test_it_matches_the_port_the_request_names(port: int, expected: bool) -> None:
    matcher = PortRequestMatcher(port)

    assert await matcher.matches(ServerRequest("GET", "http://example.com:8000/")) is expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("uri", "port", "expected"),
    [
        ("http://example.com/", 80, True),
        ("http://example.com/", 443, False),
        ("https://example.com/", 443, True),
        ("https://example.com/", 80, False),
        # The standard port of the scheme says nothing the scheme does not, so a URI
        # carrying it reads the same as one leaving it out.
        ("https://example.com:443/", 443, True),
    ],
)
async def test_it_falls_back_to_the_port_the_scheme_stands_for(
    uri: str, port: int, expected: bool
) -> None:
    matcher = PortRequestMatcher(port)

    assert await matcher.matches(ServerRequest("GET", uri)) is expected
