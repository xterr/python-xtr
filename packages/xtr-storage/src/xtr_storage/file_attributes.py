"""What a storage knows about one file."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_storage.visibility import Visibility

__all__ = ["FileAttributes"]


@final
@dataclass(frozen=True, slots=True)
class FileAttributes:
    """One file, as a listing or a metadata answer describes it.

    Everything but the path is optional because backends answer different
    questions for the same file: a listing may carry sizes and no MIME type,
    and a metadata call fills in the one field it was asked for, leaving the
    rest alone rather than paying for a second round trip. ``None`` therefore
    means "not asked, or not known here" — never "empty".

    Attributes:
        path: Where the file is, relative to the storage's root, with no
            leading slash: one file has one path, whoever wrote it.
        file_size: Its size in bytes.
        visibility: Who may read it.
        last_modified: When it last changed, in whole seconds since the epoch.
        mime_type: What it holds.
        extra_metadata: Whatever else the backend said about it.
    """

    path: str
    file_size: int | None = None
    visibility: Visibility | None = None
    last_modified: int | None = None
    mime_type: str | None = None
    extra_metadata: Mapping[str, object] = field(default_factory=dict[str, object])

    def __post_init__(self) -> None:
        """Drop a leading slash, so ``/a.txt`` and ``a.txt`` are one file, not two."""
        object.__setattr__(self, "path", self.path.lstrip("/"))

    @property
    def type(self) -> str:
        """What this entry is, for code sorting a listing without a type check."""
        return "file"

    @property
    def is_file(self) -> bool:
        """Whether this entry is a file. Always true here."""
        return True

    @property
    def is_dir(self) -> bool:
        """Whether this entry is a directory. Always false here."""
        return False

    def with_path(self, path: str) -> FileAttributes:
        """Return the same file described at another path.

        What a prefixing adapter or a mount manager needs: the backend answered
        about its own path, and the caller must be told about theirs, with every
        other field the backend gave kept intact.

        Args:
            path: The path to describe this file at.

        Returns:
            A new instance; this one is unchanged.
        """
        return replace(self, path=path)

    def to_dict(self) -> dict[str, object]:
        """Return every field under its name, for a log line, a cache or a payload."""
        return {
            "type": self.type,
            "path": self.path,
            "file_size": self.file_size,
            "visibility": self.visibility,
            "last_modified": self.last_modified,
            "mime_type": self.mime_type,
            "extra_metadata": self.extra_metadata,
        }
