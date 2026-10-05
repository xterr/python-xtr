"""What a storage knows about one directory."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_storage.visibility import Visibility

__all__ = ["DirectoryAttributes"]


@final
@dataclass(frozen=True, slots=True)
class DirectoryAttributes:
    """One directory, as a listing describes it.

    There is no size and no MIME type here, and that is the point of a separate
    type: a directory has neither, so asking is a mistake the type system can
    catch rather than a field that is forever ``None``.

    Attributes:
        path: Where the directory is, relative to the storage's root, with no
            slash at either end — a backend that names directories ``a/b/``
            and one that names them ``a/b`` describe the same place.
        visibility: Who may read it.
        last_modified: When it last changed, in whole seconds since the epoch.
        extra_metadata: Whatever else the backend said about it.
    """

    path: str
    visibility: Visibility | None = None
    last_modified: int | None = None
    extra_metadata: Mapping[str, object] = field(default_factory=dict[str, object])

    def __post_init__(self) -> None:
        """Drop the slashes at both ends, so one directory has one path."""
        object.__setattr__(self, "path", self.path.strip("/"))

    @property
    def type(self) -> str:
        """What this entry is, for code sorting a listing without a type check."""
        return "dir"

    @property
    def is_file(self) -> bool:
        """Whether this entry is a file. Always false here."""
        return False

    @property
    def is_dir(self) -> bool:
        """Whether this entry is a directory. Always true here."""
        return True

    def with_path(self, path: str) -> DirectoryAttributes:
        """Return the same directory described at another path.

        What a prefixing adapter or a mount manager needs: the backend answered
        about its own path, and the caller must be told about theirs.

        Args:
            path: The path to describe this directory at.

        Returns:
            A new instance; this one is unchanged.
        """
        return replace(self, path=path)

    def to_dict(self) -> dict[str, object]:
        """Return every field under its name, for a log line, a cache or a payload."""
        return {
            "type": self.type,
            "path": self.path,
            "visibility": self.visibility,
            "last_modified": self.last_modified,
            "extra_metadata": self.extra_metadata,
        }
