"""A client that answers from a script and holds nothing of its own."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

from typing_extensions import Unpack

from xtr_http_client import MockHttpClient

if TYPE_CHECKING:
    from xtr_http_client_contracts import RequestOptions
    from xtr_http_message_contracts import RequestInterface

    from xtr_http_client.mock_http_client import ResponseFactory
    from xtr_http_client.response import MockResponse

__all__ = ["FakeClient"]


@final
class FakeClient:
    """Answers like a scripted client, without being one that can be reset.

    Every client this package ships that keeps something between requests
    also offers a ``reset`` to drop it. This is the other kind — it keeps
    nothing — so a test of a wrapper can show what the wrapper does when
    there is no ``reset`` behind it to call.
    """

    def __init__(self, response_factory: ResponseFactory | None = None) -> None:
        """Answer from ``response_factory``, as a scripted client would."""
        self.client = MockHttpClient(response_factory)

    async def request(
        self,
        method: str,
        url: str,
        **options: Unpack[RequestOptions],
    ) -> MockResponse:
        """Answer a request for ``method`` and ``url`` from the script."""
        return await self.client.request(method, url, **options)

    async def send_request(
        self,
        request: RequestInterface,
        **options: Unpack[RequestOptions],
    ) -> MockResponse:
        """Answer ``request`` from the script."""
        return await self.client.send_request(request, **options)

    def with_options(self, **options: Unpack[RequestOptions]) -> Self:
        """Return this client: it has no defaults of its own to narrow."""
        del options

        return self
