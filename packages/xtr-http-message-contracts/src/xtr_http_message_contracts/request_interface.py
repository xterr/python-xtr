"""A request on its way out, as a client sends it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

from .message_interface import MessageInterface

if TYPE_CHECKING:
    from .uri_interface import UriInterface

__all__ = ["RequestInterface"]


@runtime_checkable
class RequestInterface(MessageInterface, Protocol):
    """An outgoing, client-side request.

    On top of what every message carries — a protocol version, headers and a
    body — a request carries a method and a URI.

    A request being built must take its ``Host`` header from the URI it is
    given whenever no ``Host`` header was given with it.

    Requests are immutable. Every ``with_*`` method keeps the instance it was
    called on as it was and returns one carrying the change.
    """

    def get_request_target(self) -> str:
        """Return the request-target of the message.

        That is the target as it will go out for a client, as it came in for a
        server, or exactly as :meth:`with_request_target` set it.

        Usually it is the origin-form of the URI the request carries — the
        path with the query string after it — unless something else was set
        explicitly.

        Returns:
            The request-target, or ``"/"`` when there is no URI to build one
            from and none was set.
        """
        ...

    def with_request_target(self, request_target: str) -> Self:
        """Return an instance carrying ``request_target`` exactly as given.

        Use it where the origin-form will not do: an absolute-form target, an
        authority-form one, or the asterisk-form.

        Args:
            request_target: The request-target, taken verbatim.

        Returns:
            A new instance; this one is left as it was.
        """
        ...

    def get_method(self) -> str:
        """Return the HTTP method of the request.

        Returns:
            The method, in the case it was given in.
        """
        ...

    def with_method(self, method: str) -> Self:
        """Return an instance carrying ``method``.

        Methods are written in capitals by convention but compared with
        regard to case, so what is given should be kept as it is rather than
        recased.

        Args:
            method: The method, case-sensitive.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            ValueError: When the method is not a valid HTTP method.
        """
        ...

    def get_uri(self) -> UriInterface:
        """Return the URI the request is for.

        Returns:
            The URI of the request.
        """
        ...

    def with_uri(self, uri: UriInterface, preserve_host: bool = False) -> Self:
        """Return an instance carrying ``uri``.

        By default the ``Host`` header of the new instance follows the URI: it
        is set from the URI's host component when the URI has one, and a
        ``Host`` header already present carries over untouched when it has
        none.

        Passing ``preserve_host=True`` asks instead that an existing ``Host``
        header be kept, which plays out in three ways:

        - no ``Host`` header, or an empty one, and a URI with a host: the
          ``Host`` header of the new instance is set from the URI;
        - no ``Host`` header, or an empty one, and a URI without a host: the
          new instance gets no ``Host`` header either;
        - a ``Host`` header that is present and not empty: it is left exactly
          as it is.

        Args:
            uri: The URI the new instance is for.
            preserve_host: Whether to keep the ``Host`` header the request
                already carries.

        Returns:
            A new instance; this one is left as it was.
        """
        ...
