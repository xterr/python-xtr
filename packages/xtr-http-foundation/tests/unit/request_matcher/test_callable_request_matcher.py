"""The callable matcher defers the claim to the callable it holds."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_message import ServerRequest

from xtr_http_foundation import CallableRequestMatcher, RequestMatcherInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface


def _asks_for_ok(request: ServerRequestInterface) -> bool:
    return request.get_query_params().get("ok") == "1"


def test_it_is_a_request_matcher() -> None:
    assert isinstance(CallableRequestMatcher(_asks_for_ok), RequestMatcherInterface)


@pytest.mark.anyio
async def test_it_claims_a_request_the_callable_accepts() -> None:
    matcher = CallableRequestMatcher(_asks_for_ok)

    assert await matcher.matches(ServerRequest("GET", "https://example.com?ok=1")) is True


@pytest.mark.anyio
async def test_it_declines_a_request_the_callable_rejects() -> None:
    matcher = CallableRequestMatcher(_asks_for_ok)

    assert await matcher.matches(ServerRequest("GET", "https://example.com")) is False
