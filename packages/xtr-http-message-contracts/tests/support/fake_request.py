"""A request that satisfies the contract, for a URI with no component."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from tests.support.fake_message import FakeMessage
from tests.support.fake_uri import FakeUri

if TYPE_CHECKING:
    from xtr_http_message_contracts import UriInterface

__all__ = ["FakeRequest"]


class FakeRequest(FakeMessage):
    """Answers the request contract on top of :class:`FakeMessage`."""

    def get_request_target(self) -> str:
        return "/"

    def with_request_target(self, request_target: str) -> Self:
        del request_target
        return self

    def get_method(self) -> str:
        return "GET"

    def with_method(self, method: str) -> Self:
        del method
        return self

    def get_uri(self) -> UriInterface:
        return FakeUri()

    def with_uri(self, uri: UriInterface, preserve_host: bool = False) -> Self:
        del uri, preserve_host
        return self
