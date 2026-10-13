"""A response that also reports how many attempts it took to get it."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Self, cast, final

from typing_extensions import override
from xtr_http_client_contracts import HttpResponseInterface

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import TracebackType

    from xtr_http_message_contracts import StreamInterface

__all__ = ["with_retry_count"]


def with_retry_count(response: HttpResponseInterface, retry_count: int) -> HttpResponseInterface:
    """``response`` with ``retry_count`` among what its transfer reports.

    A response is handed over by whoever opened the transfer, and the record
    it reads from is that transfer's own; a client that wrapped another has
    nothing to write into it. So the count is added by wrapping the response
    instead — everything but ``get_info`` is the wrapped response's, which
    keeps the one body and the one record rather than copying either.

    Args:
        response: The answer the last attempt came back with.
        retry_count: How many attempts were made again before this one
            answered.

    Returns:
        A response reading exactly as ``response`` does, whose
        ``get_info("retry_count")`` is ``retry_count``.
    """
    return _RetryCountResponse(response, retry_count)


@final
class _RetryCountResponse(HttpResponseInterface):
    __slots__ = ("_inner", "_retry_count")

    def __init__(self, inner: HttpResponseInterface, retry_count: int) -> None:
        self._inner = inner
        self._retry_count = retry_count

    @override
    def get_status_code(self) -> int:
        return self._inner.get_status_code()

    @override
    def get_reason_phrase(self) -> str:
        return self._inner.get_reason_phrase()

    @override
    def with_status(self, code: int, reason_phrase: str = "") -> Self:
        return self._around(self._inner.with_status(code, reason_phrase))

    @override
    def get_protocol_version(self) -> str:
        return self._inner.get_protocol_version()

    @override
    def with_protocol_version(self, version: str) -> Self:
        return self._around(self._inner.with_protocol_version(version))

    @override
    def get_headers(self) -> Mapping[str, Sequence[str]]:
        return self._inner.get_headers()

    @override
    def has_header(self, name: str) -> bool:
        return self._inner.has_header(name)

    @override
    def get_header(self, name: str) -> Sequence[str]:
        return self._inner.get_header(name)

    @override
    def get_header_line(self, name: str) -> str:
        return self._inner.get_header_line(name)

    @override
    def with_header(self, name: str, value: str | Sequence[str]) -> Self:
        return self._around(self._inner.with_header(name, value))

    @override
    def with_added_header(self, name: str, value: str | Sequence[str]) -> Self:
        return self._around(self._inner.with_added_header(name, value))

    @override
    def without_header(self, name: str) -> Self:
        return self._around(self._inner.without_header(name))

    @override
    def get_body(self) -> StreamInterface:
        return self._inner.get_body()

    @override
    def with_body(self, body: StreamInterface) -> Self:
        return self._around(self._inner.with_body(body))

    @override
    def get_info(self, key: str | None = None) -> object:
        if key is None:
            whole = self._inner.get_info()
            entries = (
                dict(cast("Mapping[str, object]", whole)) if isinstance(whole, Mapping) else {}
            )
            entries["retry_count"] = self._retry_count

            return entries
        if key == "retry_count":
            return self._retry_count

        return self._inner.get_info(key)

    @override
    async def cancel(self) -> None:
        await self._inner.cancel()

    @override
    async def get_content(self, throw: bool = True) -> bytes:
        return await self._inner.get_content(throw)

    @override
    async def to_array(self, throw: bool = True) -> dict[str, object]:
        return await self._inner.to_array(throw)

    @override
    async def __aenter__(self) -> Self:
        _ = await self._inner.__aenter__()

        return self

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._inner.__aexit__(exc_type, exc, traceback)

    def _around(self, inner: HttpResponseInterface) -> Self:
        return type(self)(inner, self._retry_count)
