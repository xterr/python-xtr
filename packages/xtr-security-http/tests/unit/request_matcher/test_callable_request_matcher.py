"""The callable matcher defers the claim to the callable it holds."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_foundation.request_matcher_interface import RequestMatcherInterface

from tests.support.messages import make_message
from xtr_security_http.request_matcher.callable_request_matcher import CallableRequestMatcher

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

pytestmark = pytest.mark.anyio


def _asks_for_ok(message: ServerRequestInterface) -> bool:
    return message.get_query_params().get("ok") == "1"


def test_it_is_a_request_matcher() -> None:
    assert isinstance(CallableRequestMatcher(_asks_for_ok), RequestMatcherInterface)


async def test_it_claims_a_message_the_callable_accepts() -> None:
    matcher = CallableRequestMatcher(_asks_for_ok)

    assert await matcher.matches(make_message(query="ok=1")) is True


async def test_it_declines_a_message_the_callable_rejects() -> None:
    matcher = CallableRequestMatcher(_asks_for_ok)

    assert await matcher.matches(make_message()) is False
