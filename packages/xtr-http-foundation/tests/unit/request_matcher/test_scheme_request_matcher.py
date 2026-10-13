"""The scheme of a request, against the ones a matcher names."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_message import ServerRequest

from xtr_http_foundation import SchemeRequestMatcher

if TYPE_CHECKING:
    from collections.abc import Sequence


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("request_scheme", "named", "is_match"),
    [
        ("http", "http", True),
        ("http", "HTTP", True),
        ("https", "https", True),
        ("http", "ftp", False),
        ("http", "ftp, http", True),
        ("http", "FTP, HTTP", True),
        ("http", ["http", "ftp"], True),
        ("http", ["http,ftp"], True),
    ],
)
async def test_it_matches_the_scheme(
    request_scheme: str, named: Sequence[str] | str, is_match: bool
) -> None:
    over_http = ServerRequest("GET", "http://example.com/")
    over_https = ServerRequest("GET", "https://example.com/")
    matcher = SchemeRequestMatcher(named)

    if not is_match:
        assert await matcher.matches(over_http) is False
        assert await matcher.matches(over_https) is False
    elif request_scheme == "https":
        assert await matcher.matches(over_http) is False
        assert await matcher.matches(over_https) is True
    else:
        assert await matcher.matches(over_https) is False
        assert await matcher.matches(over_http) is True


@pytest.mark.anyio
async def test_it_claims_every_request_when_it_names_no_scheme() -> None:
    matcher = SchemeRequestMatcher([])

    assert await matcher.matches(ServerRequest("GET", "sftp://example.com")) is True
