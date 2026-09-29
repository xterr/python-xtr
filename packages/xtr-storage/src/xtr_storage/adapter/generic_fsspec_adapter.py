"""Any filesystem a caller already has, used as a storage.

The named adapters cover the backends this library has an opinion about. This
one covers the rest: a caller builds the filesystem — with whatever credentials,
tuning and extras that backend takes — and hands it over, keeping every choice
about the connection on their side of the line and every choice about paths,
options and errors on this one.

What it cannot do it says plainly. A filesystem arriving from outside tells this
adapter nothing about whether the backend behind it has a notion of who may read
a file, so visibility is refused rather than guessed at; a backend whose
visibility matters deserves an adapter that knows how to set it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_storage.adapter.fsspec_adapter import FsspecAdapter

if TYPE_CHECKING:
    from fsspec import (  # pyright: ignore[reportMissingTypeStubs] -- fsspec ships no type information; imported only to type the filesystem a caller hands over
        AbstractFileSystem,
    )

__all__ = ["GenericFsspecAdapter"]


@final
class GenericFsspecAdapter(FsspecAdapter):
    """A storage adapter over a filesystem somebody else built.

    The instance is used exactly as given and never reconfigured: it is the
    caller's, built the way they wanted, and it stays open when this adapter is
    closed so the rest of their code may go on using it.

    Reading, writing, listing, moving and metadata all work — they are the same
    calls whatever the backend. Visibility is not offered: see the module
    docstring for why.
    """

    _filesystem: AbstractFileSystem

    def __init__(self, filesystem: AbstractFileSystem, root: str = "") -> None:
        """Keep the filesystem and the root, and touch neither.

        Args:
            filesystem: The filesystem to store through, already built.
            root: What every path is stored under — a directory, a key prefix.
                Empty stores at the filesystem's own root.
        """
        super().__init__(root)
        self._filesystem = filesystem

    @override
    def _create_filesystem(self) -> AbstractFileSystem:
        """Hand back the filesystem the caller gave; there is nothing to build."""
        return self._filesystem
