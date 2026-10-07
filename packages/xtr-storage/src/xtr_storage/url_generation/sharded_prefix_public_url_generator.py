"""Spreading files across several addresses by a stable hash of the path."""

from __future__ import annotations

import zlib
from typing import TYPE_CHECKING, final
from urllib.parse import quote

from typing_extensions import override

from xtr_storage.exception import InvalidArgumentError
from xtr_storage.path.path_prefixer import PathPrefixer
from xtr_storage.url_generation.public_url_generator_interface import PublicUrlGeneratorInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_storage.config import Config

__all__ = ["ShardedPrefixPublicUrlGenerator"]


@final
class ShardedPrefixPublicUrlGenerator(PublicUrlGeneratorInterface):
    """Picks one of several addresses per file, so no single host serves everything.

    Several delivery hosts publish the same store; spreading files over them
    keeps any one from carrying the whole load. The choice is a hash of the
    path rather than a counter, so the same file always resolves to the same
    host — an address stays quotable and a browser's cache stays warm — while
    different files land evenly across the hosts.
    """

    __slots__ = ("_prefixers",)

    def __init__(self, prefixes: Sequence[str]) -> None:
        """Fix the addresses files are spread over.

        Args:
            prefixes: The hosts, each a base a file may be reachable from. Order
                matters, since a path's host is chosen by its position.

        Raises:
            InvalidArgumentError: When no prefix is given, since there would be
                nothing to place a file under.
        """
        if len(prefixes) == 0:
            raise InvalidArgumentError("at least one prefix is required to shard public urls")

        self._prefixers = tuple(PathPrefixer(prefix, "/") for prefix in prefixes)

    @override
    async def public_url(self, path: str, config: Config) -> str:
        """Return ``path`` joined to the host its hash selects.

        Args:
            path: The file to address, already normalized.
            config: The options in force; the hosts are fixed, so they change
                nothing here.

        Returns:
            The chosen host followed by the path, with exactly one separator
            between.
        """
        del config  # the hosts are fixed at construction; a call cannot move them

        index = zlib.crc32(path.encode()) % len(self._prefixers)

        return self._prefixers[index].prefix_path(quote(path, safe="/"))
