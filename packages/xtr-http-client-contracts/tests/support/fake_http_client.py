"""A client that answers from memory and records what it was asked for."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

from typing_extensions import Unpack

from tests.support.fake_response import FakeResponse

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import RequestInterface

    from xtr_http_client_contracts import HttpResponseInterface, RequestOptions

__all__ = ["FakeHttpClient"]


@final
class FakeHttpClient:
    """Hands out one prepared response and remembers every call.

    The options a request was made with are kept as a plain mapping: what a
    test wants to read back is what was passed, not a shape to merge again.
    """

    def __init__(
        self,
        response: HttpResponseInterface | None = None,
        default_options: Mapping[str, object] | None = None,
    ) -> None:
        self.response: HttpResponseInterface = response if response is not None else FakeResponse()
        self.default_options: Mapping[str, object] = dict(default_options or {})
        self.calls: list[tuple[str, str, Mapping[str, object]]] = []

    async def request(
        self,
        method: str,
        url: str,
        **options: Unpack[RequestOptions],
    ) -> HttpResponseInterface:
        self.calls.append((method, url, {**self.default_options, **options}))
        return self.response

    async def send_request(
        self,
        request: RequestInterface,
        **options: Unpack[RequestOptions],
    ) -> HttpResponseInterface:
        return await self.request(request.get_method(), str(request.get_uri()), **options)

    def with_options(self, **options: Unpack[RequestOptions]) -> Self:
        return type(self)(self.response, {**self.default_options, **options})
