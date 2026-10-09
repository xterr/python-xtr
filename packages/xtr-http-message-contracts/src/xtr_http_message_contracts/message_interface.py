"""What a request and a response have in common."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from .stream_interface import StreamInterface

__all__ = ["MessageInterface"]


@runtime_checkable
class MessageInterface(Protocol):
    """An HTTP message: a protocol version, headers and a body.

    Requests travel from a client to a server and responses back the other
    way; everything they share is here.

    Messages are immutable. Every ``with_*`` method keeps the instance it was
    called on as it was and returns one carrying the change, so a message
    handed around cannot be altered behind the back of whoever handed it on.
    """

    def get_protocol_version(self) -> str:
        """Return the HTTP version of the message.

        Returns:
            The version number alone, such as ``"1.1"`` or ``"1.0"`` — never
            the protocol name with it.
        """
        ...

    def with_protocol_version(self, version: str) -> Self:
        """Return an instance carrying ``version``.

        Args:
            version: The HTTP version number alone, such as ``"1.1"``.

        Returns:
            A new instance; this one is left as it was.
        """
        ...

    def get_headers(self) -> Mapping[str, Sequence[str]]:
        """Return every header, each name mapped to all of its values.

        A name comes back in the case it was first given in, even though names
        are matched without regard to case elsewhere, so a message can be
        written out the way it arrived:

        ```python
        for name, values in message.get_headers().items():
            print(f"{name}: {', '.join(values)}")
        ```

        Returns:
            Each header name as it will go over the wire, mapped to the
            values recorded under it.
        """
        ...

    def has_header(self, name: str) -> bool:
        """Tell whether a header is present, matching ``name`` without case.

        Args:
            name: The header name, in any case.

        Returns:
            ``True`` when some header name matches ``name`` ignoring case;
            ``False`` when none does.
        """
        ...

    def get_header(self, name: str) -> Sequence[str]:
        """Return every value recorded under a header, matched without case.

        Args:
            name: The header name, in any case.

        Returns:
            All the values under that header, in order. A header the message
            does not carry gives an empty sequence.
        """
        ...

    def get_header_line(self, name: str) -> str:
        """Return the values of a header joined with commas, matched without case.

        Not every header can be written this way; where comma-joining would
        change the meaning, read :meth:`get_header` and join the values with
        whatever separator that header calls for.

        Args:
            name: The header name, in any case.

        Returns:
            The values joined with commas. A header the message does not
            carry gives an empty string.
        """
        ...

    def with_header(self, name: str, value: str | Sequence[str]) -> Self:
        """Return an instance whose ``name`` header holds ``value`` and nothing else.

        Whatever was recorded under that header is replaced. The case of
        ``name`` is kept and is what :meth:`get_headers` reports, even though
        the header it replaces is found without regard to case.

        Args:
            name: The header name, in any case.
            value: One value, or every value the header is to hold.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            ValueError: When the name or a value is not a valid header name or
                value.
        """
        ...

    def with_added_header(self, name: str, value: str | Sequence[str]) -> Self:
        """Return an instance with ``value`` appended to the ``name`` header.

        What the header already held stays; the new values go after it. A
        header the message did not carry is added.

        Args:
            name: The header name, in any case.
            value: One value, or every value to append.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            ValueError: When the name or a value is not a valid header name or
                value.
        """
        ...

    def without_header(self, name: str) -> Self:
        """Return an instance with the ``name`` header gone.

        The header to drop is found without regard to case.

        Args:
            name: The header name, in any case.

        Returns:
            A new instance; this one is left as it was.
        """
        ...

    def get_body(self) -> StreamInterface:
        """Return the body of the message.

        Returns:
            The body, as a stream.
        """
        ...

    def with_body(self, body: StreamInterface) -> Self:
        """Return an instance carrying ``body``.

        Args:
            body: The stream the new instance reads its body from.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            ValueError: When the body cannot be used as one.
        """
        ...
