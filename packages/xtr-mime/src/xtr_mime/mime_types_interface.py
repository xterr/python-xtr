"""Maps MIME types to file extensions and back, and guesses the MIME type of files."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .mime_type_guesser_interface import MimeTypeGuesserInterface

__all__ = ["MimeTypesInterface"]


@runtime_checkable
class MimeTypesInterface(MimeTypeGuesserInterface, Protocol):
    """A table of MIME types and the extensions files of each type end in.

    Several extensions can share a type and several types an extension, so both lookups answer
    a list, the preferred entry first: the first extension is the one to give a file of that
    type, the first type the one to send a file with that extension as. Extensions are written
    without their leading dot.
    """

    def get_extensions(self, mime_type: str) -> list[str]:
        """Return the extensions of files of ``mime_type``, the preferred one first.

        Returns:
            The extensions, or an empty list for a type the table does not know.
        """
        ...

    def get_mime_types(self, extension: str) -> list[str]:
        """Return the MIME types of files ending in ``extension``, the preferred one first.

        Returns:
            The MIME types, or an empty list for an extension the table does not know.
        """
        ...
