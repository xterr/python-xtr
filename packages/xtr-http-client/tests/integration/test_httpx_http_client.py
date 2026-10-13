"""The connection-opening client, run against the contract's conformance suite."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

import pytest
from typing_extensions import Unpack, override
from xtr_http_client_contracts import HttpClientInterface
from xtr_http_client_contracts.testing import HttpClientTestCase

from xtr_http_client import HttpxHttpClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping
    from typing import Self

    from xtr_http_client_contracts import HttpResponseInterface, RequestOptions
    from xtr_http_message_contracts import RequestInterface

_OPENED: list[HttpxHttpClient] = []
_ANSWERED: list[HttpResponseInterface] = []


@final
class _RecordingClient(HttpClientInterface):
    """A client that keeps every response it hands out, for the fixture to close.

    The suite leaves bodies unread on purpose — abandoning a transfer is part of what it
    checks — so nothing in it closes a response, and an unclosed body is collected with the
    file it was kept in still open. Recording them out here is what lets the run close every
    body it opened without the suite knowing anything about it.
    """

    __slots__ = ("_answered", "_client")

    def __init__(
        self,
        client: HttpClientInterface,
        answered: list[HttpResponseInterface],
    ) -> None:
        self._client = client
        self._answered = answered

    @override
    async def request(
        self,
        method: str,
        url: str,
        **options: Unpack[RequestOptions],
    ) -> HttpResponseInterface:
        return self._recorded(await self._client.request(method, url, **options))

    @override
    async def send_request(
        self,
        request: RequestInterface,
        **options: Unpack[RequestOptions],
    ) -> HttpResponseInterface:
        return self._recorded(await self._client.send_request(request, **options))

    @override
    def with_options(self, **options: Unpack[RequestOptions]) -> Self:
        return type(self)(self._client.with_options(**options), self._answered)

    def _recorded(self, response: HttpResponseInterface) -> HttpResponseInterface:
        self._answered.append(response)

        return response


class TestHttpxHttpClient(HttpClientTestCase):
    __test__: ClassVar[bool] = True

    skipped_tests: ClassVar[Mapping[str, str]] = {
        "test_http_version": "the backend has no way to send HTTP/1.0",
        "test_timeout_is_not_a_fatal_error": (
            "a read that runs out of time ends the connection, so there is no body left to resume"
        ),
    }

    @pytest.fixture(autouse=True)
    async def _close_what_the_test_opened(self) -> AsyncIterator[None]:
        _OPENED.clear()
        _ANSWERED.clear()
        yield
        while _ANSWERED:
            await _ANSWERED.pop().get_body().close()
        while _OPENED:
            await _OPENED.pop().aclose()

    @override
    def create_client(self) -> HttpClientInterface:
        client = HttpxHttpClient()
        _OPENED.append(client)

        return _RecordingClient(client, _ANSWERED)
