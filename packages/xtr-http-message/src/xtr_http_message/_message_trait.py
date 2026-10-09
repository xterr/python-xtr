"""What a request and a response have in common, in one place."""

from __future__ import annotations

import copy
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar, Self

from ._ascii import lower
from .exception import InvalidArgumentError
from .stream import Stream

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import BinaryIO

    from xtr_http_message_contracts import StreamInterface

__all__ = ["MessageTrait"]

_DEFAULT_PROTOCOL = "1.1"

# A header name is one or more token characters and nothing else, so that no
# name can carry the delimiters that would let it inject a header of its own.
_HEADER_NAME = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
# A header value is visible characters and inner blanks. The upper half of the
# range is written as the bytes it is, so a character above U+00FF — which no
# header field can carry undeclared — is refused rather than quietly sent.
_HEADER_VALUE = re.compile("[ \t\x21-\x7e\x80-\xff]*")
# The blanks around a header value belong to the field, not to the value.
_OPTIONAL_WHITESPACE = " \t"

_BAD_NAME = "Header name must be an RFC 7230 compatible string"
_BAD_VALUE = "Header values must be RFC 7230 compatible strings"
_NO_VALUE = "Header values must be a string or an array of strings, empty array given"


def _trimmed_value(value: object) -> str:
    """Return a header value with its surrounding blanks taken off.

    Args:
        value: What is being offered as a value.

    Returns:
        The value, trimmed.

    Raises:
        InvalidArgumentError: When it is not a header value — not a string at
            all, or a string carrying what no header field can.
    """
    if not isinstance(value, str) or _HEADER_VALUE.fullmatch(value) is None:
        raise InvalidArgumentError(_BAD_VALUE)

    return value.strip(_OPTIONAL_WHITESPACE)


def _validate_and_trim(name: str, value: object) -> list[str]:
    """Check a header against the grammar and return its values, trimmed.

    Args:
        name: The header name.
        value: One value, or every value the header is to hold. Taken as
            anything at all, so that a caller whose types went unchecked is
            told what was wrong with what it passed rather than left with a
            type error from deeper in.

    Returns:
        The values, each with its surrounding blanks taken off.

    Raises:
        InvalidArgumentError: When the name is not a header name, a value is
            not a header value, or a header is given no value at all.
    """
    if _HEADER_NAME.fullmatch(name) is None:
        raise InvalidArgumentError(_BAD_NAME)

    if isinstance(value, str):
        return [_trimmed_value(value)]

    if not isinstance(value, Sequence):
        raise InvalidArgumentError(_BAD_VALUE)

    offered: Sequence[object] = value
    if len(offered) == 0:
        raise InvalidArgumentError(_NO_VALUE)

    return [_trimmed_value(one) for one in offered]


class MessageTrait:
    """The protocol version, the headers and the body of any message.

    A mixin rather than a class of its own: nothing here is an HTTP message by
    itself, and the two things that are — a request and a response — differ in
    everything else. A subclass sets the state up in its own ``__init__``
    through :meth:`_set_headers`, then inherits every reader and every
    ``with_*`` method from here.

    Names are recorded in the case they were first given in and matched
    without regard to case, which is what the two mappings are for: one holds
    the headers under the name they will go out as, the other maps a
    lowercased name to that one.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_header_names", "_headers", "_protocol", "_stream")

    def __init__(self) -> None:
        """Start with no header, the usual protocol version and no body yet."""
        self._headers: dict[str, list[str]] = {}
        self._header_names: dict[str, str] = {}
        self._protocol: str = _DEFAULT_PROTOCOL
        self._stream: StreamInterface | None = None

    def get_protocol_version(self) -> str:
        """Return the HTTP version of the message.

        Returns:
            The version number alone, such as ``"1.1"``.
        """
        return self._protocol

    def with_protocol_version(self, version: str) -> Self:
        """Return an instance carrying ``version``.

        Args:
            version: The HTTP version number alone, such as ``"1.1"``.

        Returns:
            A new instance, or this one when the version is already that.
        """
        if self._protocol == version:
            return self

        new = self._copy()
        new._protocol = version  # noqa: SLF001 — a copy of this very class.

        return new

    def get_headers(self) -> Mapping[str, Sequence[str]]:
        """Return every header, each name mapped to all of its values.

        Returns:
            A fresh mapping of each header name, in the case it will go out
            as, to the values recorded under it. Changing what comes back
            cannot change the message.
        """
        return {name: list(values) for name, values in self._headers.items()}

    def has_header(self, name: str) -> bool:
        """Tell whether a header is present, matching ``name`` without case.

        Args:
            name: The header name, in any case.

        Returns:
            ``True`` when some header name matches ``name`` ignoring case.
        """
        return lower(name) in self._header_names

    def get_header(self, name: str) -> Sequence[str]:
        """Return every value recorded under a header, matched without case.

        Args:
            name: The header name, in any case.

        Returns:
            The values under that header, in order; an empty list for a header
            the message does not carry.
        """
        recorded = self._header_names.get(lower(name))
        if recorded is None:
            return []

        return list(self._headers[recorded])

    def get_header_line(self, name: str) -> str:
        """Return the values of a header joined with commas, matched without case.

        Args:
            name: The header name, in any case.

        Returns:
            The values joined with ``", "``; an empty string for a header the
            message does not carry.
        """
        return ", ".join(self.get_header(name))

    def with_header(self, name: str, value: str | Sequence[str]) -> Self:
        """Return an instance whose ``name`` header holds ``value`` and nothing else.

        Args:
            name: The header name, in any case. Its case is what the new
                instance will report and send, even when it replaces a header
                recorded under another.
            value: One value, or every value the header is to hold.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            InvalidArgumentError: When the name or a value is not one.
        """
        values = _validate_and_trim(name, value)
        normalized = lower(name)

        new = self._copy()
        replaced = new._header_names.get(normalized)  # noqa: SLF001 — a copy of this very class.
        if replaced is not None:
            del new._headers[replaced]  # noqa: SLF001 — a copy of this very class.
        new._header_names[normalized] = name  # noqa: SLF001 — a copy of this very class.
        new._headers[name] = values  # noqa: SLF001 — a copy of this very class.

        return new

    def with_added_header(self, name: str, value: str | Sequence[str]) -> Self:
        """Return an instance with ``value`` appended to the ``name`` header.

        Args:
            name: The header name, in any case. A header already recorded
                under another case keeps the case it has.
            value: One value, or every value to append.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            InvalidArgumentError: When the name or a value is not one.
        """
        new = self._copy()
        new._set_headers({name: value})  # noqa: SLF001 — a copy of this very class.

        return new

    def without_header(self, name: str) -> Self:
        """Return an instance with the ``name`` header gone.

        Args:
            name: The header name, in any case.

        Returns:
            A new instance, or this one when the message does not carry that
            header.
        """
        normalized = lower(name)
        recorded = self._header_names.get(normalized)
        if recorded is None:
            return self

        new = self._copy()
        del new._headers[recorded]  # noqa: SLF001 — a copy of this very class.
        del new._header_names[normalized]  # noqa: SLF001 — a copy of this very class.

        return new

    def get_body(self) -> StreamInterface:
        """Return the body of the message.

        A message built with no body has none until it is asked for: the empty
        stream is opened here, the first time, rather than for every message
        that never reads one.

        Returns:
            The body, as a stream.
        """
        if self._stream is None:
            self._stream = Stream.create()

        return self._stream

    def with_body(self, body: StreamInterface) -> Self:
        """Return an instance carrying ``body``.

        Args:
            body: The stream the new instance reads its body from.

        Returns:
            A new instance, or this one when it already reads that very
            stream.
        """
        if body is self._stream:
            return self

        new = self._copy()
        new._stream = body  # noqa: SLF001 — a copy of this very class.

        return new

    def _copy(self) -> Self:
        """Return a copy to change, leaving this instance as it is.

        The two header mappings are copied rather than shared, so that a
        change made to the copy cannot reach back into this message. The body
        is shared: a stream is the one thing here that is not a value.
        """
        new = copy.copy(self)
        new._headers = {  # noqa: SLF001 — a copy of this very class.
            name: list(values) for name, values in self._headers.items()
        }
        new._header_names = dict(self._header_names)  # noqa: SLF001 — a copy of this very class.

        return new

    def _set_headers(self, headers: Mapping[str, str | Sequence[str]]) -> None:
        """Record headers on this instance, appending to any already there.

        Only for a constructor and for :meth:`with_added_header`: it changes
        the instance it is called on, which is either brand new or a copy
        nobody else holds yet.

        Args:
            headers: Each header name mapped to one value or to several.

        Raises:
            InvalidArgumentError: When a name or a value is not one.
        """
        for name, value in headers.items():
            values = _validate_and_trim(name, value)
            normalized = lower(name)
            recorded = self._header_names.get(normalized)
            if recorded is None:
                self._header_names[normalized] = name
                self._headers[name] = values
            else:
                self._headers[recorded].extend(values)

    def _set_body(self, body: bytes | BinaryIO | StreamInterface | None) -> None:
        """Record the body of a message being built, leaving an empty one unopened.

        Only for a constructor. Nothing is opened for a message with no body:
        :meth:`get_body` sees to that if it is ever asked for.

        Args:
            body: The payload, in any of the shapes a stream is built from, or
                ``None``.
        """
        if body is not None and body != b"":
            self._stream = Stream.create(body)

    def _put_header_first(self, name: str, values: list[str]) -> None:
        """Record a header in front of every other, dropping where it was.

        Only for a constructor and for the ``with_*`` methods of a request: it
        changes the instance it is called on. A request sends its ``Host``
        header first, which is the one thing the order of these mappings is
        for.

        Args:
            name: The header name, already in the case it will go out as.
            values: What the header is to hold.
        """
        rest = [(other, held) for other, held in self._headers.items() if other != name]
        self._headers = {name: values}
        self._headers.update(rest)
