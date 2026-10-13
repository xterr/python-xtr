"""A chain claims a request only when every matcher it holds claims it."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_http_message import ServerRequest

from xtr_http_foundation import ChainRequestMatcher, RequestMatcherInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface


@final
class _Answering(RequestMatcherInterface):
    """A matcher that answers what it was built with, and counts the asking."""

    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.asked = 0

    @override
    async def matches(self, request: ServerRequestInterface) -> bool:
        self.asked += 1
        return self.answer


@pytest.mark.anyio
async def test_it_claims_a_request_every_matcher_claims() -> None:
    matcher = ChainRequestMatcher([_Answering(answer=True), _Answering(answer=True)])

    assert await matcher.matches(ServerRequest("GET", "/")) is True


@pytest.mark.anyio
async def test_it_refuses_a_request_one_matcher_refuses() -> None:
    matcher = ChainRequestMatcher([_Answering(answer=True), _Answering(answer=False)])

    assert await matcher.matches(ServerRequest("GET", "/")) is False


@pytest.mark.anyio
async def test_it_claims_every_request_when_it_chains_nothing() -> None:
    matcher = ChainRequestMatcher([])

    assert await matcher.matches(ServerRequest("GET", "/")) is True


@pytest.mark.anyio
async def test_it_stops_asking_once_one_matcher_refused() -> None:
    refusing = _Answering(answer=False)
    never_asked = _Answering(answer=True)
    matcher = ChainRequestMatcher([refusing, never_asked])

    assert await matcher.matches(ServerRequest("GET", "/")) is False
    assert (refusing.asked, never_asked.asked) == (1, 0)


@pytest.mark.anyio
async def test_it_can_be_asked_twice() -> None:
    matcher = ChainRequestMatcher(iter([_Answering(answer=True)]))
    request = ServerRequest("GET", "/")

    assert await matcher.matches(request) is True
    assert await matcher.matches(request) is True
