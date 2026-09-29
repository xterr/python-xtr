"""A media-type detector that reads a file's extension and nothing else."""

from __future__ import annotations

from mimetypes import MimeTypes
from typing import Final, final

from typing_extensions import override

from .mime_type_detector_interface import MimeTypeDetectorInterface

__all__ = ["ExtensionMimeTypeDetector"]

# Extensions mapped explicitly so a guess is the same on every machine and every
# interpreter version, whether or not the built-in table happens to carry them.
_EXPLICIT_TYPES: Final[tuple[tuple[str, str], ...]] = (
    ("image/svg+xml", ".svg"),
    ("text/markdown", ".md"),
    ("image/webp", ".webp"),
    ("application/json", ".json"),
)


@final
class ExtensionMimeTypeDetector(MimeTypeDetectorInterface):
    """Guesses a media type from the extension, deterministically across machines.

    The standard library's shared registry reads system files (such as
    ``/etc/mime.types``) on first use, so the same extension can resolve
    differently on two machines. This detector instead owns a private
    ``MimeTypes(filenames=())`` instance: passing no filenames keeps it from
    reading any system file, while it still loads the interpreter's built-in
    table, so the mapping depends only on the standard library, not on the host.
    A handful of extensions are then added explicitly to close the remaining gap
    between interpreter versions.

    The lookup is case-insensitive — the underlying table folds the extension —
    and an extension it does not recognise yields ``None`` rather than a guess.
    """

    __slots__ = ("_mime_types",)

    def __init__(self) -> None:
        """Build the private table and register the explicit extensions."""
        self._mime_types = MimeTypes(filenames=())
        for mime_type, extension in _EXPLICIT_TYPES:
            self._mime_types.add_type(mime_type, extension)

    @override
    def detect_from_path(self, path: str) -> str | None:
        """Return the media type ``path``'s extension names, or ``None``."""
        mime_type, _ = self._mime_types.guess_type(path)
        return mime_type
