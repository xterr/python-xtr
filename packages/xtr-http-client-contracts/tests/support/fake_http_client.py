"""A client that answers from memory and records what it was asked for."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Self, final

from typing_extensions import Unpack

from tests.support.fake_chunk import FakeChunk
from tests.support.fake_response import FakeResponse
from tests.support.fake_response_stream import FakeResponseStream

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_http_client_contracts import (
        ChunkInterface,
        RequestOptions,
        ResponseInterface,
        ResponseStreamInterface,
    )

__all__ = ["FakeHttpClient"]


@final
class FakeHttpClient:
    """Hands out one prepared response and remembers every call.

    The options a request was made with are kept as a plain mapping: what a
    test wants to read back is what was passed, not a shape to merge again.
    """

    def __init__(
        self,
        response: ResponseInterface | None = None,
        default_options: Mapping[str, object] | None = None,
    ) -> None:
        self.response: ResponseInterface = response if response is not None else FakeResponse()
        self.default_options: Mapping[str, object] = dict(default_options or {})
        self.calls: list[tuple[str, str, Mapping[str, object]]] = []

    async def request(
        self,
        method: str,
        url: str,
        **options: Unpack[RequestOptions],
    ) -> ResponseInterface:
        self.calls.append((method, url, {**self.default_options, **options}))
        return self.response

    def stream(
        self,
        responses: ResponseInterface | Iterable[ResponseInterface],
        timeout: float | None = None,
    ) -> ResponseStreamInterface:
        del timeout
        answered: Sequence[ResponseInterface] = (
            tuple(responses) if isinstance(responses, Iterable) else (responses,)
        )
        chunk: ChunkInterface = FakeChunk(first=True)
        return FakeResponseStream([(response, chunk) for response in answered])

    def with_options(self, **options: Unpack[RequestOptions]) -> Self:
        return type(self)(self.response, {**self.default_options, **options})
