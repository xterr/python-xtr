"""Serving every file under one fixed address."""

from __future__ import annotations

from typing import TYPE_CHECKING, final
from urllib.parse import quote

from typing_extensions import override

from xtr_storage.path.path_prefixer import PathPrefixer
from xtr_storage.url_generation.public_url_generator_interface import PublicUrlGeneratorInterface

if TYPE_CHECKING:
    from xtr_storage.config import Config

__all__ = ["PrefixPublicUrlGenerator"]


@final
class PrefixPublicUrlGenerator(PublicUrlGeneratorInterface):
    """Joins every path to one address, the way a single delivery host serves a store.

    The commonest case: one content delivery host publishes the whole store, so
    a file's address is that host followed by the file's path. The prefix owns
    that join, reusing the same path arithmetic the adapters use to sit under a
    root, so a trailing slash on the prefix or a leading slash on the path never
    doubles or drops one.
    """

    __slots__ = ("_prefixer",)

    def __init__(self, prefix: str) -> None:
        """Fix the address every path is placed under.

        Args:
            prefix: The host and any base path files are reachable from, such as
                ``"https://cdn.example.com/assets/"``.
        """
        self._prefixer = PathPrefixer(prefix, "/")

    @override
    async def public_url(self, path: str, config: Config) -> str:
        """Return ``path`` joined to the fixed prefix.

        Args:
            path: The file to address, already normalized.
            config: The options in force; the prefix is fixed, so they change
                nothing here.

        Returns:
            The prefix followed by the path, with exactly one separator between.
        """
        del config  # the address is fixed at construction; a call cannot move it

        return self._prefixer.prefix_path(quote(path, safe="/"))
