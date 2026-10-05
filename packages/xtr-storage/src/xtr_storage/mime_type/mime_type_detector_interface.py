"""Guessing a file's media type from its path alone."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["MimeTypeDetectorInterface"]


@runtime_checkable
class MimeTypeDetectorInterface(Protocol):
    """Turns a path into a media type without ever opening the file.

    An adapter asks for a file's media type when the backend does not store one
    of its own. The path is all it has — the bytes may live on another machine
    and fetching them only to sniff a type would be a second round trip — so a
    detector decides from the name and returns ``None`` when the name says
    nothing it recognises.
    """

    def detect_from_path(self, path: str) -> str | None:
        """Return the media type ``path`` names, or ``None`` when it is unknown.

        Args:
            path: The location of the file, whether or not it exists. Only its
                trailing extension is read.

        Returns:
            A media type such as ``"image/svg+xml"``, or ``None`` when the
            extension maps to nothing known.
        """
        ...
