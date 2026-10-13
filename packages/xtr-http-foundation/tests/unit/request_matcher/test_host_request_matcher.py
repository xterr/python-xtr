"""The host of a request, held to a regular expression."""

from __future__ import annotations

import pytest
from xtr_http_message import ServerRequest

from xtr_http_foundation import HostRequestMatcher
from xtr_http_foundation.exception import InvalidArgumentError


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("pattern", "is_match"),
    [
        (r".*\.example\.com", True),
        (r"\.example\.com$", True),
        (r"^.*\.example\.com$", True),
        (r".*\.sensio\.com", False),
        # The host is matched without regard to case, so these read the same as the above.
        (r".*\.example\.COM", True),
        (r"\.example\.COM$", True),
        (r"^.*\.example\.COM$", True),
        (r".*\.sensio\.COM", False),
    ],
)
async def test_it_matches_the_host(pattern: str, is_match: bool) -> None:
    matcher = HostRequestMatcher(pattern)
    request = ServerRequest("GET", "http://foo.example.com/")

    assert await matcher.matches(request) is is_match


def test_it_refuses_an_expression_that_does_not_read_as_one() -> None:
    with pytest.raises(InvalidArgumentError, match=r'"\(unclosed" is not a valid'):
        _ = HostRequestMatcher("(unclosed")
