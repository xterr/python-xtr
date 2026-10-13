"""The head of a client response, answered by the message it holds."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_http_message_contracts import ResponseInterface as MessageResponseInterface
    from xtr_http_message_contracts import StreamInterface

__all__ = ["MessageResponseMixin"]


class MessageResponseMixin:
    """Everything the message contract asks of a response, answered by an HTTP message.

    A client response is an HTTP response before it is a transfer, and an
    HTTP message already knows how to be one: its status, reason phrase,
    protocol version and headers — matched without regard to case — and its
    ``with_*`` copies. So all of that is the message's, held here and asked. A
    copy differs from the response it was made from in its message alone, and
    keeps everything else, so copying a response to add a header neither
    starts its transfer again nor loses track of it.

    ``get_status_code()`` and ``get_headers()`` count as looking at the
    status, which is what leaving an ``async with`` block checks before it
    lets a 3xx, 4xx or 5xx go unreported. Looking also means the head no longer
    needs announcing, so a run started afterwards opens without a first chunk.
    """

    __slots__: tuple[str, ...] = ("_first_pending", "_looked", "_message")

    _message: MessageResponseInterface
    _looked: bool
    _first_pending: bool

    def __init__(self, message: MessageResponseInterface) -> None:
        """Answer from ``message``, whose head nobody has looked at yet."""
        self._message = message
        self._looked = False
        self._first_pending = True

    def get_protocol_version(self) -> str:
        """Return the HTTP version the response came over."""
        return self._message.get_protocol_version()

    def with_protocol_version(self, version: str) -> Self:
        """Return a copy whose message carries another protocol version."""
        return self._around(self._message.with_protocol_version(version))

    def get_headers(self) -> Mapping[str, Sequence[str]]:
        """Return every header, which counts as looking at the status."""
        self._look()
        return self._message.get_headers()

    def has_header(self, name: str) -> bool:
        """Tell whether the response carries ``name``, matched without regard to case."""
        return self._message.has_header(name)

    def get_header(self, name: str) -> Sequence[str]:
        """Return the values of ``name``, or none when the response does not carry it."""
        return self._message.get_header(name)

    def get_header_line(self, name: str) -> str:
        """Return the values of ``name`` joined by commas."""
        return self._message.get_header_line(name)

    def with_header(self, name: str, value: str | Sequence[str]) -> Self:
        """Return a copy whose message carries ``value`` as the only value of ``name``."""
        return self._around(self._message.with_header(name, value))

    def with_added_header(self, name: str, value: str | Sequence[str]) -> Self:
        """Return a copy whose message carries ``value`` after the values of ``name``."""
        return self._around(self._message.with_added_header(name, value))

    def without_header(self, name: str) -> Self:
        """Return a copy whose message does not carry ``name``."""
        return self._around(self._message.without_header(name))

    def get_body(self) -> StreamInterface:
        """Return the body, read off the transfer as it is asked for."""
        return self._message.get_body()

    def with_body(self, body: StreamInterface) -> Self:
        """Return a copy whose message hands out ``body`` instead."""
        return self._around(self._message.with_body(body))

    def get_status_code(self) -> int:
        """Return the status code, which counts as looking at it."""
        self._look()
        return self._message.get_status_code()

    def with_status(self, code: int, reason_phrase: str = "") -> Self:
        """Return a copy whose message carries another status."""
        return self._around(self._message.with_status(code, reason_phrase))

    def get_reason_phrase(self) -> str:
        """Return the reason phrase the status line carried."""
        return self._message.get_reason_phrase()

    def _look(self) -> None:
        self._looked = True
        self._first_pending = False

    def _around(self, message: MessageResponseInterface) -> Self:
        """Return a copy of this response around ``message``, sharing all the rest.

        The message hands itself back when a change would change nothing, and
        so does this.
        """
        if message is self._message:
            return self
        changed = copy.copy(self)
        changed._message = message  # noqa: SLF001 — a copy of this very class.
        return changed
