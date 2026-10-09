"""What went wrong, or did not, while a file was being uploaded."""

from __future__ import annotations

from enum import IntEnum

__all__ = ["UploadError"]


class UploadError(IntEnum):
    """The outcome an uploaded file reports from :meth:`get_error`.

    The standard this package translates describes the outcome as one of a set
    of numbered constants its host language defines. Nothing here defines
    them, so they are gathered into this enumeration, keeping the numbers the
    wire and the standard already agree on — which is why ``5`` is missing:
    that number was never assigned.

    Being an :class:`~enum.IntEnum`, a member compares and passes as the
    integer the contract calls for, so an implementation may hold either.
    """

    OK = 0
    """The file arrived whole; nothing went wrong."""

    INI_SIZE = 1
    """The file was larger than the limit the server configuration allows."""

    FORM_SIZE = 2
    """The file was larger than the limit the submitted form itself named."""

    PARTIAL = 3
    """The upload stopped part way; only some of the file arrived."""

    NO_FILE = 4
    """The field was submitted with no file in it."""

    NO_TMP_DIR = 6
    """There was nowhere to put the incoming file while it was being received."""

    CANT_WRITE = 7
    """The incoming file could not be written to where it was being kept."""

    EXTENSION = 8
    """Something the server had loaded refused the upload."""
