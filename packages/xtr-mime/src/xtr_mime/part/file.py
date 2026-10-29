"""A file on disk a part reads only when it is rendered."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, final

from xtr_mime.mime_types import MimeTypes

if TYPE_CHECKING:
    from os import PathLike

__all__ = ["File"]

_DEFAULT_CONTENT_TYPE = "application/octet-stream"


@final
class File:
    """A path, with the name and type an attachment of it gets.

    Nothing is read when the file is named: a part built from it reads it when rendered, so
    an email holding large attachments costs nothing until it is sent.
    """

    __slots__ = ("_filename", "_path")

    def __init__(self, path: str | PathLike[str], filename: str | None = None) -> None:
        """Keep ``path`` and the name to show for it, its base name when ``None``."""
        self._path: str = os.fspath(path)
        self._filename: str | None = filename

    def get_path(self) -> str:
        """Return the path, as given."""
        return self._path

    def get_content_type(self) -> str:
        """Return the type of a file with this extension, ``application/octet-stream`` if none.

        The extension decides, not the content: the file is not read.
        """
        _, dot, extension = Path(self._path).name.rpartition(".")
        mime_types = MimeTypes.get_default().get_mime_types(extension.lower()) if dot else []
        return mime_types[0] if mime_types else _DEFAULT_CONTENT_TYPE

    def get_size(self) -> int:
        """Return the size of the file in bytes, read from the file system.

        Raises:
            OSError: The file cannot be looked at.
        """
        return Path(self._path).stat().st_size

    def get_filename(self) -> str:
        """Return the name given, else the base name of the path."""
        if self._filename is None:
            self._filename = Path(self._path).name
        return self._filename
