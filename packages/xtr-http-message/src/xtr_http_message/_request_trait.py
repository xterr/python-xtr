"""What an outgoing request and an incoming one have in common, in one place."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar, Self

from ._message_trait import MessageTrait
from .exception import InvalidArgumentError
from .uri import Uri

if TYPE_CHECKING:
    from xtr_http_message_contracts import UriInterface

__all__ = ["RequestTrait"]

_WHITESPACE = re.compile(r"\s")
_HOST = "Host"
_NORMALIZED_HOST = "host"


class RequestTrait(MessageTrait):
    """The method, the request-target and the URI of any request.

    A mixin, for the same reason
    :class:`~xtr_http_message._message_trait.MessageTrait` is one: a request
    going out and a request that arrived carry all of this and differ in what
    else they carry. It extends that one, since every request is a message.

    The ``Host`` header follows the URI unless a caller asks for it not to,
    and is sent in front of every other header.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_method", "_request_target", "_uri")

    def __init__(self) -> None:
        """Start with no method, no request-target set by hand and no URI."""
        super().__init__()
        self._method: str = ""
        self._request_target: str | None = None
        self._uri: UriInterface = Uri()

    def get_request_target(self) -> str:
        """Return the request-target of the message.

        Built from the URI — the path with the query string after it — unless
        :meth:`with_request_target` set one by hand, in which case that is
        returned exactly as it was given.

        Returns:
            The request-target, which is ``"/"`` when the URI has no path to
            build one from.
        """
        if self._request_target is not None:
            return self._request_target

        target = self._uri.get_path()
        if target == "":
            target = "/"

        query = self._uri.get_query()
        if query != "":
            target = f"{target}?{query}"

        return target

    def with_request_target(self, request_target: str) -> Self:
        """Return an instance carrying ``request_target`` exactly as given.

        Args:
            request_target: The request-target, taken verbatim. Use it where
                the path-and-query form will not do: an absolute URI, an
                authority alone, or the asterisk.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            InvalidArgumentError: When the request-target carries whitespace,
                which would split the request line in two.
        """
        if _WHITESPACE.search(request_target) is not None:
            raise InvalidArgumentError("Invalid request target provided; cannot contain whitespace")

        new = self._copy()
        new._request_target = request_target  # noqa: SLF001 — a copy of this very class.

        return new

    def get_method(self) -> str:
        """Return the HTTP method of the request.

        Returns:
            The method, in the case it was given in.
        """
        return self._method

    def with_method(self, method: str) -> Self:
        """Return an instance carrying ``method``.

        Args:
            method: The method, kept exactly as given: methods are compared
                with regard to case, so recasing one would change it.

        Returns:
            A new instance; this one is left as it was.
        """
        new = self._copy()
        new._method = method  # noqa: SLF001 — a copy of this very class.

        return new

    def get_uri(self) -> UriInterface:
        """Return the URI the request is for.

        Returns:
            The URI of the request.
        """
        return self._uri

    def with_uri(self, uri: UriInterface, preserve_host: bool = False) -> Self:
        """Return an instance carrying ``uri``.

        Args:
            uri: The URI the new instance is for.
            preserve_host: Whether to keep a ``Host`` header the request
                already carries. Left to its default, the header follows the
                new URI.

        Returns:
            A new instance, or this one when it is already for that very URI.
        """
        if uri is self._uri:
            return self

        new = self._copy()
        new._uri = uri  # noqa: SLF001 — a copy of this very class.

        if not preserve_host or not self.has_header(_HOST):
            new._update_host_from_uri()  # noqa: SLF001 — a copy of this very class.

        return new

    def _update_host_from_uri(self) -> None:
        """Set the ``Host`` header from the URI, in front of every other header.

        Only for a constructor and for :meth:`with_uri`: it changes the
        instance it is called on. A URI with no host leaves the header alone,
        since there would be nothing to put in it.
        """
        host = self._uri.get_host()
        if host == "":
            return

        port = self._uri.get_port()
        if port is not None:
            host = f"{host}:{port}"

        recorded = self._header_names.get(_NORMALIZED_HOST)
        if recorded is None:
            recorded = _HOST
            self._header_names[_NORMALIZED_HOST] = recorded

        self._put_header_first(recorded, [host])
