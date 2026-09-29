"""Turning a stored path into a lasting address."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_storage.config import Config

__all__ = ["PublicUrlGeneratorInterface"]


@runtime_checkable
class PublicUrlGeneratorInterface(Protocol):
    """Says where a stored file is reachable from, so the application need not serve it.

    Two kinds of thing satisfy this. An adapter whose backend owns an address
    for every object it holds, which a storage discovers at runtime. And a
    standalone generator put in front of a storage — a content delivery host
    the files are published under, which the backend knows nothing about.

    Producing an address is not a permission check: the address may well lead
    to a file nobody but its owner may read.
    """

    async def public_url(self, path: str, config: Config) -> str:
        """Return a lasting address for the file at ``path``.

        Args:
            path: The file to address, already normalized.
            config: The options in force.

        Returns:
            An absolute URL.

        Raises:
            UnableToGeneratePublicUrlError: When no address can be built for
                this file — which a chain of generators takes as its cue to try
                the next one.
        """
        ...
