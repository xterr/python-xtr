"""A response that has already arrived, built from the fields it answers with."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Self, cast, final

from xtr_http_client_contracts import (
    ClientError,
    DecodingError,
    RedirectionError,
    ServerError,
)

from tests.support.fake_stream import FakeStream

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from types import TracebackType

    from xtr_http_message_contracts import StreamInterface

__all__ = ["FakeResponse"]


def _values(value: str | Sequence[str]) -> tuple[str, ...]:
    return (value,) if isinstance(value, str) else tuple(value)


def _no_headers() -> Mapping[str, Sequence[str]]:
    return {}


@final
@dataclass(slots=True)
class FakeResponse:
    """A whole response in memory, with the transfer info composed from its fields.

    ``response_headers`` is the raw head as it came off the wire — the status
    line first, then one line per header — because that is what the error
    message builder refines a message from. ``content_reads`` counts the calls
    to ``get_content()``, which is how a test proves the builder read the body
    only when the head said it was worth reading.
    """

    status_code: int = 200
    reason_phrase: str = "OK"
    protocol_version: str = "1.1"
    headers: Mapping[str, Sequence[str]] = field(default_factory=_no_headers)
    response_headers: object = ()
    body: StreamInterface = field(default_factory=FakeStream)
    method: str = "GET"
    url: str = "https://example.com/"
    user_data: object = None
    error: str | None = None
    canceled: bool = False
    content_reads: int = 0

    def get_protocol_version(self) -> str:
        return self.protocol_version

    def with_protocol_version(self, version: str) -> Self:
        return replace(self, protocol_version=version)

    def get_headers(self) -> Mapping[str, Sequence[str]]:
        return self.headers

    def has_header(self, name: str) -> bool:
        return any(key.lower() == name.lower() for key in self.headers)

    def get_header(self, name: str) -> Sequence[str]:
        lowered = name.lower()
        for key, values in self.headers.items():
            if key.lower() == lowered:
                return values
        return ()

    def get_header_line(self, name: str) -> str:
        return ", ".join(self.get_header(name))

    def with_header(self, name: str, value: str | Sequence[str]) -> Self:
        return replace(self, headers={**self._without(name), name: _values(value)})

    def with_added_header(self, name: str, value: str | Sequence[str]) -> Self:
        kept = self._name_of(name)
        values = (*self.get_header(name), *_values(value))
        return replace(self, headers={**self._without(name), kept: values})

    def without_header(self, name: str) -> Self:
        return replace(self, headers=self._without(name))

    def get_body(self) -> StreamInterface:
        return self.body

    def with_body(self, body: StreamInterface) -> Self:
        return replace(self, body=body)

    def get_status_code(self) -> int:
        return self.status_code

    def with_status(self, code: int, reason_phrase: str = "") -> Self:
        return replace(self, status_code=code, reason_phrase=reason_phrase)

    def get_reason_phrase(self) -> str:
        return self.reason_phrase

    def get_info(self, key: str | None = None) -> object:
        info: dict[str, object] = {
            "canceled": self.canceled,
            "error": self.error,
            "http_code": self.status_code,
            "http_method": self.method,
            "redirect_count": 0,
            "redirect_url": None,
            "response_headers": self.response_headers,
            "start_time": 0.0,
            "url": self.url,
            "user_data": self.user_data,
        }
        if key is None:
            return info
        return info.get(key)

    async def cancel(self) -> None:
        self.canceled = True
        await self.body.close()

    async def get_content(self, throw: bool = True) -> bytes:
        self.content_reads += 1
        if throw:
            self._raise_for_status()
        return await self.body.get_contents()

    async def to_array(self, throw: bool = True) -> dict[str, object]:
        content = await self.get_content(throw)
        try:
            decoded = cast("object", json.loads(content))
        except ValueError as error:
            raise DecodingError(str(error)) from error
        if not isinstance(decoded, dict):
            raise DecodingError(
                f'JSON content was expected to decode to an object, "{type(decoded).__name__}" '
                f'returned for "{self.url}".'
            )
        return cast("dict[str, object]", decoded)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        await self.body.close()

    def _raise_for_status(self) -> None:
        reason = f'HTTP {self.status_code} returned for "{self.url}".'
        if 300 <= self.status_code < 400:
            raise RedirectionError(self, reason)
        if 400 <= self.status_code < 500:
            raise ClientError(self, reason)
        if 500 <= self.status_code < 600:
            raise ServerError(self, reason)

    def _without(self, name: str) -> dict[str, Sequence[str]]:
        lowered = name.lower()
        return {key: values for key, values in self.headers.items() if key.lower() != lowered}

    def _name_of(self, name: str) -> str:
        lowered = name.lower()
        return next((key for key in self.headers if key.lower() == lowered), name)
