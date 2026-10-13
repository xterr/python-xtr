"""The method of a request, against the ones a matcher names."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_message import ServerRequest

from xtr_http_foundation import MethodRequestMatcher

if TYPE_CHECKING:
    from collections.abc import Sequence


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("named", "is_match"),
    [
        ("get", True),
        ("post,get", True),
        ("post, get", True),
        ("post,GET", True),
        (["get", "post"], True),
        ("post", False),
        ("GET", True),
        (["GET", "POST"], True),
        ("POST", False),
    ],
)
async def test_it_matches_the_method(named: Sequence[str] | str, is_match: bool) -> None:
    matcher = MethodRequestMatcher(named)

    assert await matcher.matches(ServerRequest("GET", "/")) is is_match


@pytest.mark.anyio
async def test_it_claims_every_request_when_it_names_no_method() -> None:
    matcher = MethodRequestMatcher([])

    assert await matcher.matches(ServerRequest("POST", "https://example.com")) is True
