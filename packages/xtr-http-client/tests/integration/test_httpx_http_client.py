"""The connection-opening client, run against the contract's conformance suite."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest
from typing_extensions import override
from xtr_http_client_contracts.testing import HttpClientTestCase

from xtr_http_client import HttpxHttpClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

_OPENED: list[HttpxHttpClient] = []


class TestHttpxHttpClient(HttpClientTestCase):
    __test__: ClassVar[bool] = True

    skipped_tests: ClassVar[Mapping[str, str]] = {
        "test_http_version": "the backend has no way to send HTTP/1.0",
        "test_timeout_is_not_a_fatal_error": (
            "a read that runs out of time ends the connection, so there is no body left to resume"
        ),
        "test_request_is_send_request_of_the_same_request": (
            "the echo answers the client's own port, which no two connections share"
        ),
    }

    @pytest.fixture(autouse=True)
    async def _close_what_the_test_opened(self) -> AsyncIterator[None]:
        _OPENED.clear()
        yield
        while _OPENED:
            await _OPENED.pop().aclose()

    @override
    def create_client(self) -> HttpxHttpClient:
        client = HttpxHttpClient()
        _OPENED.append(client)

        return client
