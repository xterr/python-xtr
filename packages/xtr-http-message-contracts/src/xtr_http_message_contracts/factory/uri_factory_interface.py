"""Build a URI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts.uri_interface import UriInterface

__all__ = ["UriFactoryInterface"]


@runtime_checkable
class UriFactoryInterface(Protocol):
    """Makes a URI, so that a caller need not name the class that is one."""

    def create_uri(self, uri: str = "") -> UriInterface:
        """Return a new URI parsed from ``uri``.

        Args:
            uri: The URI as text; empty for a URI with no components at all.

        Returns:
            The URI.

        Raises:
            ValueError: When the text cannot be parsed as a URI.
        """
        ...
