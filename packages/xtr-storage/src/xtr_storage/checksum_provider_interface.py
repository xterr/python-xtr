"""Backends that already know a file's digest."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_storage.config import Config

__all__ = ["ChecksumProviderInterface"]


@runtime_checkable
class ChecksumProviderInterface(Protocol):
    """An adapter that can answer for a digest without sending the file back.

    Object stores keep a digest beside every object, and asking for it is one
    small request; computing the same digest means downloading the whole file.
    So an adapter that has one says so by satisfying this, and a storage checks
    at runtime before falling back to reading the bytes itself.

    Optional by design: an adapter that does not implement this is not lacking
    anything — the fallback gives the same answer, more slowly.
    """

    async def checksum(self, path: str, config: Config) -> str:
        """Return the digest the backend holds for the file at ``path``.

        Args:
            path: The file to digest, already normalized.
            config: The options in force, naming the algorithm among them.

        Returns:
            The digest, in the form the backend keeps it.

        Raises:
            ChecksumAlgorithmNotSupportedError: When the backend keeps no
                digest of that algorithm — a storage takes this as its cue to
                compute one from the file's bytes instead.
            UnableToProvideChecksumError: When the backend could not be asked.
        """
        ...
