"""The MIME types files have, the extensions MIME types use, and guessing a file's type."""

from __future__ import annotations

import mimetypes
from pathlib import PurePath
from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override

from ._readable_file import ensure_readable_file
from .magic_mime_type_guesser import MagicMimeTypeGuesser
from .mime_types_interface import MimeTypesInterface

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from .mime_type_guesser_interface import MimeTypeGuesserInterface

__all__ = ["MimeTypes"]


@final
class MimeTypes(MimeTypesInterface):
    """Maps MIME types to extensions and back, and guesses the MIME type of a file.

    The table is the standard library's built-in one (``mimetypes.MimeTypes()``): its registered
    types first, then the common unregistered ones (``image/jpg`` after ``image/jpeg``). It is
    deliberately not the module-level database, which also reads the host's ``mime.types``
    files: a message must not change with the machine that renders it. An extra map adds types
    or extensions the table lacks, and ranks before it. A lookup that finds nothing as written
    tries again in lower case.

    To guess a file's type, the registered guessers that can run here are asked, the last
    registered first, and the first answer wins. A new table registers a
    :class:`~xtr_mime.MagicMimeTypeGuesser`, which reads the file's content where libmagic is
    installed. When no guesser answers, the file's extension is looked up in the table — so,
    unlike a guesser that needs a native library, this one can always guess, but without
    libmagic it names a file by what it is called, not by what it holds.

    :meth:`get_default` keeps one shared table for code that has none handed to it; it is the
    only state shared between instances.
    """

    __slots__ = ("_extensions", "_guessers", "_mime_types")

    _default: ClassVar[MimeTypes | None] = None

    _extensions: dict[str, list[str]]
    _mime_types: dict[str, list[str]]
    _guessers: list[MimeTypeGuesserInterface]

    def __init__(self, extra_map: Mapping[str, Sequence[str]] | None = None) -> None:
        """Build the table, ``extra_map`` first, and register the libmagic guesser.

        Args:
            extra_map: Extensions by MIME type, without their leading dot, ranked before the
                standard table's: ``{"application/mbox": ["mbox"]}``.
        """
        self._extensions = {}
        self._mime_types = {}
        for mime_type, extensions in (extra_map or {}).items():
            for extension in extensions:
                self._add(mime_type, extension)

        # The first one built in a process also initialises the standard library's module-level
        # database, which reads the host's files; only the built-in table is read from here.
        standard = mimetypes.MimeTypes()
        for types_map in (standard.types_map[True], standard.types_map[False]):
            for dotted_extension, mime_type in types_map.items():
                self._add(mime_type, dotted_extension.removeprefix("."))

        self._guessers = []
        self.register_guesser(MagicMimeTypeGuesser())

    @classmethod
    def get_default(cls) -> MimeTypes:
        """Return the shared table, built on first use unless :meth:`set_default` gave one."""
        if cls._default is None:
            cls._default = cls()
        return cls._default

    @classmethod
    def set_default(cls, default: MimeTypes) -> None:
        """Make ``default`` the table :meth:`get_default` returns from now on."""
        cls._default = default

    def register_guesser(self, guesser: MimeTypeGuesserInterface) -> None:
        """Ask ``guesser`` before every guesser registered so far, the libmagic one included."""
        self._guessers.insert(0, guesser)

    @override
    def get_extensions(self, mime_type: str) -> list[str]:
        """Return the extensions of files of ``mime_type``, the preferred one first."""
        extensions = self._extensions.get(mime_type) or self._extensions.get(mime_type.lower(), [])
        return list(extensions)

    @override
    def get_mime_types(self, extension: str) -> list[str]:
        """Return the MIME types of files ending in ``extension``, the preferred one first."""
        mime_types = self._mime_types.get(extension) or self._mime_types.get(extension.lower(), [])
        return list(mime_types)

    @override
    def is_guesser_supported(self) -> bool:
        """Answer ``True``: the table answers whenever no registered guesser can."""
        return True

    @override
    def guess_mime_type(self, path: str) -> str | None:
        """Name the type of the file at ``path``: its guessers' answer, else its extension's.

        Returns:
            The MIME type, or ``None`` when no guesser answers and the table does not know the
            file's extension.

        Raises:
            InvalidArgumentError: When ``path`` does not name a file this process may read.
        """
        for guesser in self._guessers:
            if not guesser.is_guesser_supported():
                continue
            mime_type = guesser.guess_mime_type(path)
            if mime_type is not None:
                return mime_type

        ensure_readable_file(path)
        mime_types = self.get_mime_types(PurePath(path).suffix.removeprefix("."))
        return mime_types[0] if mime_types else None

    def _add(self, mime_type: str, extension: str) -> None:
        extensions = self._extensions.setdefault(mime_type, [])
        if extension not in extensions:
            extensions.append(extension)
        mime_types = self._mime_types.setdefault(extension, [])
        if mime_type not in mime_types:
            mime_types.append(mime_type)
