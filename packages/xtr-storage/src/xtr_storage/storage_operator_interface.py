"""A whole storage: reading, writing, and the addresses files are reachable at."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from xtr_storage.storage_reader_interface import StorageReaderInterface
from xtr_storage.storage_writer_interface import StorageWriterInterface

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

__all__ = ["StorageOperatorInterface"]


@runtime_checkable
class StorageOperatorInterface(StorageReaderInterface, StorageWriterInterface, Protocol):
    """Everything a storage does, and what code depending on one asks for.

    Reading and writing arrive by inheritance — a storage that can do both is
    the ordinary case, and the two halves exist so that narrower code can ask
    for one. What is added here is the third thing a storage is used for:
    handing out an address a browser can fetch a file from, without the
    application serving the bytes itself.

    Whether an address can be produced at all depends on the backend and on
    what the storage was configured with, so both methods may refuse.
    """

    async def public_url(self, path: str, config: Mapping[str, object] | None = None) -> str:
        """Return a lasting address the file at ``path`` is reachable at.

        Args:
            path: The file to address.
            config: Options for this call alone.

        Returns:
            An absolute URL, which says nothing about whether the file is
            actually readable by whoever follows it — that is its visibility.

        Raises:
            UnableToGeneratePublicUrlError: When nothing was configured to
                build one, or building it failed.
        """
        ...

    async def temporary_url(
        self,
        path: str,
        expires_at: datetime,
        config: Mapping[str, object] | None = None,
    ) -> str:
        """Return an address for the file at ``path`` that stops working later.

        How a private file is handed to a browser for one download: the address
        carries its own permission, and the permission runs out.

        Args:
            path: The file to address.
            expires_at: When the address stops working. Must carry a timezone,
                since a moment without one names a different instant on every
                machine that reads it.
            config: Options for this call alone.

        Returns:
            An absolute URL, valid until ``expires_at``.

        Raises:
            InvalidArgumentError: When ``expires_at`` carries no timezone.
            UnableToGenerateTemporaryUrlError: When nothing was configured to
                build one, or building it failed.
        """
        ...

    async def checksum(self, path: str, config: Mapping[str, object] | None = None) -> str:
        """Return a digest of the file at ``path``, for comparing it with another.

        Args:
            path: The file to digest.
            config: Options for this call alone, the algorithm among them.

        Returns:
            The digest in lowercase hexadecimal, unless the algorithm asked for
            is one the backend keeps in a form of its own.

        Raises:
            InvalidArgumentError: When the algorithm asked for is unknown.
            UnableToProvideChecksumError: When the file could not be digested.
        """
        ...
