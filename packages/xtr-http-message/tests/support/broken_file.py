"""A binary file object that can do nothing, while reporting that it can do everything."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, NoReturn

from typing_extensions import override

if TYPE_CHECKING:
    from _typeshed import ReadableBuffer

__all__ = ["BrokenFile"]

_BROKEN = "the device has gone away"


class BrokenFile(io.BytesIO):
    """A buffer whose every operation fails at the device under it.

    It reports itself open, seekable, readable and writable, and then refuses
    each of the three: a real one is a file on a mount that has gone away, or
    one on a disk that has filled up — a file object that answered every
    question truthfully when it was asked, and fails once it is used.

    This is the only way to reach what a stream does when an operation it had
    every reason to expect to work does not, and it carries its own contract
    test.
    """

    @override
    def seek(self, pos: int, whence: int = io.SEEK_SET, /) -> NoReturn:
        """Refuse to move the cursor.

        Args:
            pos: Ignored.
            whence: Ignored.

        Raises:
            OSError: Always.
        """
        del pos, whence
        raise OSError(_BROKEN)

    @override
    def read(self, size: int | None = -1, /) -> NoReturn:
        """Refuse to read.

        Args:
            size: Ignored.

        Raises:
            OSError: Always.
        """
        del size
        raise OSError(_BROKEN)

    @override
    def write(self, buffer: ReadableBuffer, /) -> NoReturn:
        """Refuse to write.

        Args:
            buffer: Ignored.

        Raises:
            OSError: Always.
        """
        del buffer
        raise OSError(_BROKEN)
