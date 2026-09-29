"""Asking a run of generators in turn until one answers."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_storage.exception import UnableToGeneratePublicUrlError
from xtr_storage.url_generation.public_url_generator_interface import PublicUrlGeneratorInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_storage.config import Config

__all__ = ["ChainedPublicUrlGenerator"]


@final
class ChainedPublicUrlGenerator(PublicUrlGeneratorInterface):
    """Tries generators in order, taking the first address any of them will give.

    A store may be reachable more than one way — a fast delivery host for most
    files, a signing generator for the few that need it — and which applies is
    decided per file rather than up front. Each generator declines a file it
    cannot address by raising, which is this chain's cue to try the next; only
    when every one has declined does the chain itself decline.
    """

    __slots__ = ("_generators",)

    def __init__(self, generators: Sequence[PublicUrlGeneratorInterface]) -> None:
        """Fix the generators to consult, in the order they are consulted.

        Args:
            generators: The generators to try; an empty run always declines,
                since there is nothing to ask.
        """
        self._generators = tuple(generators)

    @override
    async def public_url(self, path: str, config: Config) -> str:
        """Return the first address any generator gives for ``path``.

        Args:
            path: The file to address, already normalized.
            config: The options in force, passed on to each generator unchanged.

        Returns:
            The address of the first generator that does not decline.

        Raises:
            UnableToGeneratePublicUrlError: When every generator declined, or
                there were none to ask.
        """
        for generator in self._generators:
            try:
                return await generator.public_url(path, config)
            except UnableToGeneratePublicUrlError:
                continue

        raise UnableToGeneratePublicUrlError(
            path,
            "no generator in the chain could build a public url",
        )
